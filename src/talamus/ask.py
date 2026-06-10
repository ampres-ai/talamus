from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from talamus.adapters.llm import LLMProvider
from talamus.budget import context_budget, estimate_tokens, fit_to_budget
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
    from talamus.indexes import postings_path, sqlite_path
    from talamus.indexes import search_index as query_persistent_index

    budget = context_budget(budget_tokens)
    ontology = load_ontology(paths)
    items: list[dict] = []
    if sqlite_path(paths).is_file() or postings_path(paths).is_file():
        # M4 path: seeds from the persistent index, then 1-hop ontology expansion
        seed_titles = [h["title"] for h in query_persistent_index(paths, question, limit=limit)]
        for title in _expand_with_ontology(seed_titles, ontology, limit):
            path = _note_path(paths, title)
            if not path.is_file():
                continue
            route = "index" if title in seed_titles else "graph"
            items.append(
                {"route": route, "path": path.as_posix(), "content": path.read_text("utf-8")}
            )
        return ContextBundle(question=question, items=fit_to_budget(items, budget))

    # legacy path for brains indexed before M4: caller-provided graph + BM25
    seed_titles = [str(node["label"]) for node in query_graph(graph, question, limit=limit)]
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


_ROUTE_PROMPT = """Data la MAPPA dei domini (id | nome: descrizione) e una DOMANDA, restituisci
SOLO gli id dei domini pertinenti, separati da virgola (es. dom-retrieval, dom-tempo).
Nessun'altra parola.

MAPPA:
{map}

DOMANDA: {question}
"""


def _overview_bundle(
    paths: TalamusPaths,
    question: str,
    llm: LLMProvider,
    limit: int = 8,
    trace: dict | None = None,
) -> ContextBundle:
    """Route via the domain overview. Domains are picked by **stable id** (F3.7/F3.8):
    the LLM answers with ids, parsed and validated against the map — substring
    matching on names survives only as a fallback for pre-id overviews."""
    overview = load_overview(paths)
    if not overview:
        return ContextBundle(question=question, items=[])
    domain_map = "\n".join(
        f"- {d.get('id', '?')} | {d.get('name', '')}: {d.get('description', '')}" for d in overview
    )
    raw = llm.complete(_ROUTE_PROMPT.format(map=domain_map, question=question))
    valid_ids = {str(d["id"]) for d in overview if d.get("id")}
    chosen_ids = [token for token in re.findall(r"[a-z0-9-]+", raw.lower()) if token in valid_ids]
    titles: list[str] = []
    fallback = False
    if chosen_ids:
        for domain in overview:
            if str(domain.get("id", "")) in chosen_ids:
                titles.extend(domain.get("members", []))
    else:  # pre-id overviews or unparseable response: legacy name matching
        fallback = True
        lower = raw.lower()
        for domain in overview:
            name = str(domain.get("name", "")).lower()
            if name and name in lower:
                titles.extend(domain.get("members", []))
    if trace is not None:
        trace["domains_available"] = [str(d.get("id") or d.get("name", "?")) for d in overview]
        trace["domains_chosen"] = chosen_ids
        trace["routing_fallback"] = fallback
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


def answer_question(
    paths: TalamusPaths,
    question: str,
    llm: LLMProvider,
    extra_items: list[dict] | None = None,
    trace: dict | None = None,
) -> str:
    """Answer from the brain. ``extra_items`` lets callers append cross-brain
    context (real note contents with scope markers) before the budget cut.
    Pass a dict as ``trace`` to get the route explained (F3.10): domains, route,
    notes read, context tokens, whether fallbacks fired."""
    bundle = _overview_bundle(paths, question, llm, trace=trace)
    route = "overview" if bundle.items else "none"
    if not bundle.items:
        graph = (
            load_graph(paths.graph_file)
            if paths.graph_file.is_file()
            else {"nodes": {}, "edges": []}
        )
        search = BM25Index.load(paths.index_file) if paths.index_file.is_file() else BM25Index()
        bundle = build_context_bundle(paths, graph, search, question)
        if bundle.items:
            route = "index"
        elif not extra_items:
            bundle = build_context_bundle(paths, graph, search, _expand_query(question, llm))
            if bundle.items:
                route = "expansion"
    all_items = [*bundle.items, *(extra_items or [])]
    if trace is not None:
        trace["route"] = route
        trace["extra_items"] = len(extra_items or [])
    if not all_items:
        return "Nessun contesto trovato nel brain per questa domanda."
    items = fit_to_budget(all_items, context_budget())
    if trace is not None:
        trace["items_read"] = [item["path"] for item in items]
        trace["context_tokens"] = sum(estimate_tokens(item["content"]) for item in items)
    context = "\n\n".join(
        f"[{idx}] {item['path']}\n{item['content']}" for idx, item in enumerate(items, start=1)
    )
    answer = llm.complete(_ANSWER_PROMPT.format(question=question, context=context)).strip()
    if not answer:
        return "Il motore non ha prodotto una risposta. Riprova o controlla l'engine."
    sources = "\n".join(
        f"[{idx}] {Path(item['path']).name}" for idx, item in enumerate(items, start=1)
    )
    return f"{answer}\n\n**Fonti:**\n{sources}"
