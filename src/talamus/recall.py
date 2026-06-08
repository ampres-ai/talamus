from __future__ import annotations

from talamus.ask import build_context_bundle
from talamus.graph import load_graph, query_graph
from talamus.naming import note_filename, note_slug
from talamus.ontology import load_ontology, neighbors
from talamus.paths import TalamusPaths
from talamus.search import BM25Index
from talamus.store import load_notes


def _load_graph_and_index(paths: TalamusPaths):
    graph = load_graph(paths.graph_file) if paths.graph_file.is_file() else {"nodes": {}, "edges": []}
    index = BM25Index.load(paths.index_file) if paths.index_file.is_file() else BM25Index()
    return graph, index


def search_notes(paths: TalamusPaths, query: str, limit: int = 5) -> list[dict]:
    """Candidati pertinenti: prima la mappa (grafo), poi ripiego testuale. {title, summary}."""
    notes_by_title = {note.title: note for note in load_notes(paths)}
    graph, index = _load_graph_and_index(paths)
    results: list[dict] = []
    seen: set[str] = set()
    for node in query_graph(graph, query, limit=limit):
        title = str(node.get("label", ""))
        note = notes_by_title.get(title)
        if note is not None and title not in seen:
            seen.add(title)
            results.append({"title": title, "summary": note.summary})
    if not results:
        slug_to_note = {note_slug(note.title): note for note in notes_by_title.values()}
        for hit in index.search(query, limit=limit):
            note = slug_to_note.get(hit["id"])
            if note is not None and note.title not in seen:
                seen.add(note.title)
                results.append({"title": note.title, "summary": note.summary})
    return results[:limit]


def read_note_text(paths: TalamusPaths, title: str) -> str | None:
    """Contenuto Markdown di una scheda dato il titolo (fallback case-insensitive)."""
    path = paths.notes / note_filename(title)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    for note in load_notes(paths):
        if note.title.lower() == title.lower():
            candidate = paths.notes / note_filename(note.title)
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
    return None


def concept_neighbors(paths: TalamusPaths, concept: str) -> list[dict]:
    """Vicini tipizzati di un concetto nella mappa (ontologia): per navigare le connessioni."""
    return neighbors(load_ontology(paths), concept)


def recall_context(paths: TalamusPaths, question: str, limit: int = 5) -> str:
    """Contesto pertinente (schede reali) per una domanda. L'agente è l'LLM: ritorna risorse, non risposte."""
    graph, index = _load_graph_and_index(paths)
    bundle = build_context_bundle(paths, graph, index, question, limit=limit)
    if not bundle.items:
        return "Nessun contesto pertinente trovato nel brain."
    return bundle.render()
