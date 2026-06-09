from __future__ import annotations

from dataclasses import dataclass

from talamus.adapters.llm import LLMProvider
from talamus.budget import context_budget, fit_to_budget
from talamus.domains import load_overview
from talamus.graph import load_graph, query_graph
from talamus.naming import note_filename
from talamus.ontology import load_ontology, neighbors
from talamus.paths import TalamusPaths
from talamus.search import BM25Index


@dataclass(frozen=True)
class ContextBundle:
    question: str
    items: list[dict]

    def render(self) -> str:
        lines = [f"Question: {self.question}", ""]
        for idx, item in enumerate(self.items, start=1):
            lines.extend([f"[{idx}] {item['path']} ({item['route']})", item["content"], ""])
        return "\n".join(lines).strip() + "\n"


def _note_path(paths: TalamusPaths, label: str):
    return paths.notes / note_filename(label)


def _expand_with_ontology(seed_titles: list[str], ontology: dict, limit: int) -> list[str]:
    """Riempie i candidati seguendo le relazioni dell'ontologia (1 salto), oltre alle parole."""
    ranked = list(seed_titles)
    for title in seed_titles:
        for neighbor in neighbors(ontology, title):
            if neighbor["title"] not in ranked:
                ranked.append(neighbor["title"])
    return ranked[:limit]


def build_context_bundle(
    paths: TalamusPaths,
    graph: dict,
    search_index: BM25Index,
    question: str,
    limit: int = 5,
    budget_tokens: int | None = None,
) -> ContextBundle:
    budget = context_budget(budget_tokens)
    ontology = load_ontology(paths)
    seed_titles = [str(node["label"]) for node in query_graph(graph, question, limit=limit)]
    items: list[dict] = []
    for title in _expand_with_ontology(seed_titles, ontology, limit):
        path = _note_path(paths, title)
        if not path.is_file():
            continue
        items.append(
            {"route": "graph", "path": path.as_posix(), "content": path.read_text(encoding="utf-8")}
        )
    if items:
        return ContextBundle(question=question, items=fit_to_budget(items, budget))

    for result in search_index.search(question, limit=limit):
        path = paths.notes / f"{result['id']}.md"
        if not path.is_file():
            continue
        items.append(
            {"route": "bm25", "path": path.as_posix(), "content": path.read_text(encoding="utf-8")}
        )
    return ContextBundle(question=question, items=fit_to_budget(items, budget))


_ROUTE_PROMPT = """Data la MAPPA dei domini (nome: descrizione) e una DOMANDA, restituisci
SOLO i nomi dei domini pertinenti, separati da virgola. Nessun'altra parola.

MAPPA:
{map}

DOMANDA: {question}
"""


def _overview_bundle(
    paths: TalamusPaths, question: str, llm: LLMProvider, limit: int = 8
) -> ContextBundle:
    """Route via the domain overview: pick the relevant domain(s), read their notes."""
    overview = load_overview(paths)
    if not overview:
        return ContextBundle(question=question, items=[])
    domain_map = "\n".join(f"- {d['name']}: {d.get('description', '')}" for d in overview)
    chosen = llm.complete(_ROUTE_PROMPT.format(map=domain_map, question=question)).lower()
    titles: list[str] = []
    for domain in overview:
        if str(domain.get("name", "")).lower() in chosen:
            titles.extend(domain.get("members", []))
    items: list[dict] = []
    for title in titles[:limit]:
        path = _note_path(paths, title)
        if path.is_file():
            items.append(
                {
                    "route": "overview",
                    "path": path.as_posix(),
                    "content": path.read_text(encoding="utf-8"),
                }
            )
    return ContextBundle(question=question, items=items)


_EXPAND_PROMPT = """Riscrivi la domanda in 3-6 parole chiave o termini tecnici per la ricerca,
separati da spazio. Restituisci SOLO i termini.

DOMANDA: {question}
"""


def _expand_query(question: str, llm: LLMProvider) -> str:
    return llm.complete(_EXPAND_PROMPT.format(question=question)).strip() or question


_ANSWER_PROMPT = """Rispondi alla domanda usando SOLO il contesto qui sotto.
Cita le schede tra parentesi quadre con il loro numero, es. [1].
Se il contesto non basta, dillo esplicitamente.

DOMANDA: {question}

CONTESTO:
{context}
"""


def answer_question(paths: TalamusPaths, question: str, llm: LLMProvider) -> str:
    bundle = _overview_bundle(paths, question, llm)
    if not bundle.items:
        graph = (
            load_graph(paths.graph_file)
            if paths.graph_file.is_file()
            else {"nodes": {}, "edges": []}
        )
        search = BM25Index.load(paths.index_file) if paths.index_file.is_file() else BM25Index()
        bundle = build_context_bundle(paths, graph, search, question)
        if not bundle.items:
            bundle = build_context_bundle(paths, graph, search, _expand_query(question, llm))
    if not bundle.items:
        return "Nessun contesto trovato nel brain per questa domanda."
    items = fit_to_budget(bundle.items, context_budget())
    context = "\n\n".join(
        f"[{idx}] {item['path']}\n{item['content']}" for idx, item in enumerate(items, start=1)
    )
    answer = llm.complete(_ANSWER_PROMPT.format(question=question, context=context)).strip()
    return answer or "Il motore non ha prodotto una risposta. Riprova o controlla l'engine."
