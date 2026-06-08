from __future__ import annotations

from dataclasses import dataclass

from talamus.adapters.llm import LLMProvider
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
) -> ContextBundle:
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
        return ContextBundle(question=question, items=items)

    for result in search_index.search(question, limit=limit):
        path = paths.notes / f"{result['id']}.md"
        if not path.is_file():
            continue
        items.append(
            {"route": "bm25", "path": path.as_posix(), "content": path.read_text(encoding="utf-8")}
        )
    return ContextBundle(question=question, items=items)


_ANSWER_PROMPT = """Rispondi alla domanda usando SOLO il contesto qui sotto.
Cita le schede tra parentesi quadre con il loro numero, es. [1].
Se il contesto non basta, dillo esplicitamente.

DOMANDA: {question}

CONTESTO:
{context}
"""


def answer_question(paths: TalamusPaths, question: str, llm: LLMProvider) -> str:
    graph = (
        load_graph(paths.graph_file) if paths.graph_file.is_file() else {"nodes": {}, "edges": []}
    )
    search = BM25Index.load(paths.index_file) if paths.index_file.is_file() else BM25Index()
    bundle = build_context_bundle(paths, graph, search, question)
    if not bundle.items:
        return "Nessun contesto trovato nel brain per questa domanda."
    context = "\n\n".join(
        f"[{idx}] {item['path']}\n{item['content']}"
        for idx, item in enumerate(bundle.items, start=1)
    )
    return llm.complete(_ANSWER_PROMPT.format(question=question, context=context))
