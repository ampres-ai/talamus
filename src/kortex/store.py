from __future__ import annotations

import json

from kortex.graph import build_graph, save_graph
from kortex.linking import NoteRegistry
from kortex.models import CanonicalNote, ProposedLink, Relation, SourceRef
from kortex.naming import note_filename, note_slug
from kortex.paths import KortexPaths
from kortex.search import BM25Index
from kortex.storage.obsidian import render_obsidian_note


def _note_from_dict(data: dict) -> CanonicalNote:
    return CanonicalNote(
        note_id=data["note_id"],
        title=data["title"],
        aliases=list(data.get("aliases", [])),
        folder=data.get("folder", ""),
        tags=list(data.get("tags", [])),
        summary=data.get("summary", ""),
        retrieval_text=data.get("retrieval_text", ""),
        body_sections=dict(data.get("body_sections", {})),
        proposed_links=[ProposedLink(**p) for p in data.get("proposed_links", [])],
        relations=[Relation(**r) for r in data.get("relations", [])],
        sources=[SourceRef(**s) for s in data.get("sources", [])],
        confidence=float(data.get("confidence", 0.8)),
    )


def load_notes(paths: KortexPaths) -> list[CanonicalNote]:
    notes: list[CanonicalNote] = []
    if not paths.notes_cache.exists():
        return notes
    for path in sorted(paths.notes_cache.glob("*.json")):
        notes.append(_note_from_dict(json.loads(path.read_text(encoding="utf-8"))))
    return notes


def write_note(paths: KortexPaths, note: CanonicalNote) -> None:
    paths.notes_cache.mkdir(parents=True, exist_ok=True)
    (paths.notes_cache / f"{note_slug(note.note_id)}.json").write_text(
        json.dumps(note.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    registry = NoteRegistry.from_notes(load_notes(paths) + [note])
    markdown = render_obsidian_note(note, registry)
    paths.notes.mkdir(parents=True, exist_ok=True)
    (paths.notes / note_filename(note.title)).write_text(markdown, encoding="utf-8")


def rebuild_indexes(paths: KortexPaths) -> None:
    notes = load_notes(paths)
    paths.cache.mkdir(parents=True, exist_ok=True)
    save_graph(paths.graph_file, build_graph(notes))
    index = BM25Index()
    for note in notes:
        haystack = " ".join(
            [note.title, " ".join(note.aliases), " ".join(note.tags), note.retrieval_text, note.summary]
        )
        index.add(note_slug(note.title), haystack)
    index.save(paths.index_file)
