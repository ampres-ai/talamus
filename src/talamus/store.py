from __future__ import annotations

import dataclasses
import json

from talamus.graph import build_graph, save_graph
from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote, ProposedLink, Relation, SourceRef
from talamus.naming import note_filename, note_slug
from talamus.noteparse import parse_note_markdown
from talamus.ontology import build_ontology, save_ontology
from talamus.paths import TalamusPaths
from talamus.search import BM25Index
from talamus.storage.obsidian import render_obsidian_note


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


def load_notes(paths: TalamusPaths) -> list[CanonicalNote]:
    notes: list[CanonicalNote] = []
    if not paths.notes_cache.exists():
        return notes
    for path in sorted(paths.notes_cache.glob("*.json")):
        notes.append(_note_from_dict(json.loads(path.read_text(encoding="utf-8"))))
    return notes


def _dedup_relations(relations: list[Relation]) -> list[Relation]:
    seen: set[tuple[str, str, str]] = set()
    out: list[Relation] = []
    for relation in relations:
        key = (relation.source, relation.relation, relation.target)
        if key not in seen:
            seen.add(key)
            out.append(relation)
    return out


def _dedup_links(links: list[ProposedLink]) -> list[ProposedLink]:
    seen: set[tuple[str, str]] = set()
    out: list[ProposedLink] = []
    for link in links:
        key = (link.anchor, link.target)
        if key not in seen:
            seen.add(key)
            out.append(link)
    return out


def merge_notes(existing: CanonicalNote, new: CanonicalNote) -> CanonicalNote:
    """Fonde due versioni dello stesso concetto: accumula le fonti, unisce i campi
    strutturati, tiene la prosa della versione con confidenza piu' alta."""
    seen_src = {(s.source_hash, s.normalized_path) for s in existing.sources}
    sources = list(existing.sources) + [
        s for s in new.sources if (s.source_hash, s.normalized_path) not in seen_src
    ]
    base = new if new.confidence > existing.confidence else existing
    return dataclasses.replace(
        base,
        aliases=list(dict.fromkeys(existing.aliases + new.aliases)),
        tags=list(dict.fromkeys(existing.tags + new.tags)),
        relations=_dedup_relations(existing.relations + new.relations),
        proposed_links=_dedup_links(existing.proposed_links + new.proposed_links),
        sources=sources,
        confidence=max(existing.confidence, new.confidence),
    )


def write_note_json(paths: TalamusPaths, note: CanonicalNote) -> None:
    paths.notes_cache.mkdir(parents=True, exist_ok=True)
    path = paths.notes_cache / f"{note_slug(note.note_id)}.json"
    if path.is_file():
        existing = _note_from_dict(json.loads(path.read_text(encoding="utf-8")))
        note = merge_notes(existing, note)
    path.write_text(json.dumps(note.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def render_note_markdown(paths: TalamusPaths, note: CanonicalNote, registry: NoteRegistry) -> None:
    markdown = render_obsidian_note(note, registry)
    paths.notes.mkdir(parents=True, exist_ok=True)
    (paths.notes / note_filename(note.title)).write_text(markdown, encoding="utf-8")


def write_note(paths: TalamusPaths, note: CanonicalNote) -> None:
    write_note_json(paths, note)
    registry = NoteRegistry.from_notes(load_notes(paths) + [note])
    render_note_markdown(paths, note, registry)


def rebuild_indexes(paths: TalamusPaths) -> None:
    notes = load_notes(paths)
    paths.cache.mkdir(parents=True, exist_ok=True)
    save_graph(paths.graph_file, build_graph(notes))
    save_ontology(paths.ontology_file, build_ontology(notes))
    index = BM25Index()
    for note in notes:
        haystack = " ".join(
            [
                note.title,
                " ".join(note.aliases),
                " ".join(note.tags),
                note.retrieval_text,
                note.summary,
            ]
        )
        index.add(note_slug(note.title), haystack)
    index.save(paths.index_file)


def reindex(paths: TalamusPaths) -> dict:
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
