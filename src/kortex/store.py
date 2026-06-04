from __future__ import annotations

import dataclasses
import json

from kortex.graph import build_graph, save_graph
from kortex.linking import NoteRegistry
from kortex.models import CanonicalNote, ProposedLink, Relation, SourceRef
from kortex.naming import note_filename, note_slug
from kortex.noteparse import parse_note_markdown
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


def write_note_json(paths: KortexPaths, note: CanonicalNote) -> None:
    paths.notes_cache.mkdir(parents=True, exist_ok=True)
    (paths.notes_cache / f"{note_slug(note.note_id)}.json").write_text(
        json.dumps(note.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )


def render_note_markdown(paths: KortexPaths, note: CanonicalNote, registry: NoteRegistry) -> None:
    markdown = render_obsidian_note(note, registry)
    paths.notes.mkdir(parents=True, exist_ok=True)
    (paths.notes / note_filename(note.title)).write_text(markdown, encoding="utf-8")


def write_note(paths: KortexPaths, note: CanonicalNote) -> None:
    write_note_json(paths, note)
    registry = NoteRegistry.from_notes(load_notes(paths) + [note])
    render_note_markdown(paths, note, registry)


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


def reindex(paths: KortexPaths) -> dict:
    """Rilegge i .md (verita' dei campi umani) e aggiorna la cache, preservando la provenienza."""
    cached = {note.note_id: note for note in load_notes(paths)}
    merged: list[CanonicalNote] = []
    if paths.notes.exists():
        for md_path in sorted(paths.notes.glob("*.md")):
            parsed = parse_note_markdown(md_path.read_text(encoding="utf-8"))
            note_id = parsed["id"] or note_slug(parsed["title"]).lower()
            if not note_id:
                continue
            base = cached.get(note_id)
            if base is not None:
                note = dataclasses.replace(
                    base,
                    title=parsed["title"] or base.title,
                    aliases=parsed["aliases"] or base.aliases,
                    tags=parsed["tags"] or base.tags,
                    summary=parsed["summary"] or base.summary,
                    body_sections=parsed["body_sections"] or base.body_sections,
                )
            else:
                note = CanonicalNote(
                    note_id=note_id,
                    title=parsed["title"],
                    aliases=parsed["aliases"],
                    folder="",
                    tags=parsed["tags"],
                    summary=parsed["summary"],
                    retrieval_text=parsed["title"],
                    body_sections=parsed["body_sections"] or {"summary": parsed["summary"]},
                    proposed_links=[],
                    relations=[],
                    sources=[],
                    confidence=0.8,
                )
            merged.append(note)

    paths.notes_cache.mkdir(parents=True, exist_ok=True)
    valid = {note_slug(note.note_id) for note in merged}
    for stale in paths.notes_cache.glob("*.json"):
        if stale.stem not in valid:
            stale.unlink()
    for note in merged:
        (paths.notes_cache / f"{note_slug(note.note_id)}.json").write_text(
            json.dumps(note.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
    rebuild_indexes(paths)
    return {"reindexed": len(merged)}
