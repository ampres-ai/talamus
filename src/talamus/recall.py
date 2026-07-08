from __future__ import annotations

from talamus.ask import build_context_bundle
from talamus.graph import load_graph
from talamus.naming import note_filename
from talamus.ontology import load_inferred_ontology, load_ontology, neighbors
from talamus.paths import TalamusPaths
from talamus.rank import rerank_candidates
from talamus.search import BM25Index
from talamus.store import load_notes


def _load_graph_and_index(paths: TalamusPaths):
    graph = (
        load_graph(paths.graph_file) if paths.graph_file.is_file() else {"nodes": {}, "edges": []}
    )
    index = BM25Index.load(paths.index_file) if paths.index_file.is_file() else BM25Index()
    return graph, index


def search_notes(paths: TalamusPaths, query: str, limit: int = 5) -> list[dict]:
    """Relevant candidates from the persistent index, reranked. {title, summary}.

    Since M4 the search queries the persistent index (sqlite/FTS5 or posting list) and
    the metadata it carries — no more loading every note on each query.
    """
    from talamus.indexes import search_index

    pool = max(limit * 2, limit)
    hits = search_index(paths, query, limit=pool)
    if not hits:
        return []
    aliases_by_title = {h["title"]: list(h.get("aliases", [])) for h in hits}
    bm25_hits = [(str(h["title"]), float(h["score"])) for h in hits]
    ranked = rerank_candidates(query, [], bm25_hits, aliases_by_title, limit=limit)
    summary_by_title = {h["title"]: h["summary"] for h in hits}
    return [{"title": title, "summary": summary_by_title.get(title, "")} for title, _ in ranked]


def read_note_text(paths: TalamusPaths, title: str) -> str | None:
    """Markdown content of a note given its title (case-insensitive fallback)."""
    path = paths.notes / note_filename(title)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    for note in load_notes(paths):
        if note.title.lower() == title.lower():
            candidate = paths.notes / note_filename(note.title)
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
    return None


def concept_neighbors(
    paths: TalamusPaths, concept: str, *, include_inferred: bool = True
) -> list[dict]:
    """Typed neighbors of a concept in the map (ontology): to navigate connections."""
    inferred = load_inferred_ontology(paths) if include_inferred else None
    return neighbors(load_ontology(paths), concept, inferred, include_inferred=include_inferred)


def recall_context(paths: TalamusPaths, question: str, limit: int = 5) -> str:
    """Relevant context (real notes) for a question.
    The agent is the LLM: it returns resources, not answers."""
    graph, index = _load_graph_and_index(paths)
    bundle = build_context_bundle(paths, graph, index, question, limit=limit)
    if not bundle.items:
        return "No relevant context found in the brain."
    return bundle.render()
