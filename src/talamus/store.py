from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime

from talamus.graph import build_graph, save_graph
from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote, ProposedLink, Relation, SourceRef
from talamus.naming import note_filename, note_slug
from talamus.noteparse import parse_note_markdown
from talamus.ontology import build_ontology, save_ontology
from talamus.paths import TalamusPaths
from talamus.search import BM25Index
from talamus.storage.obsidian import render_obsidian_note

# v3: Fase RS three-channel index (bilingual stems + trigram fields). Migration from
# any prior version = `talamus reindex` (doctor reports the stale cache; everything
# under .talamus/cache is derived/rebuildable).
CACHE_VERSION = 4  # RS4: meta carries hay_len for hub-suppression length penalty


def _write_cache_manifest(paths: TalamusPaths) -> None:
    paths.cache.mkdir(parents=True, exist_ok=True)
    paths.cache_manifest.write_text(
        json.dumps({"cache_version": CACHE_VERSION}, indent=2), encoding="utf-8"
    )


def cache_version(paths: TalamusPaths) -> int | None:
    """The cache schema version on disk, or None if missing/unreadable."""
    if not paths.cache_manifest.is_file():
        return None
    try:
        data = json.loads(paths.cache_manifest.read_text(encoding="utf-8"))
        return int(data["cache_version"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def cache_is_current(paths: TalamusPaths) -> bool:
    """True if the on-disk cache matches the current schema version."""
    return cache_version(paths) == CACHE_VERSION


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _append_history(paths: TalamusPaths, note: CanonicalNote) -> None:
    """Preserve a prior version of a note before it is overwritten (invalidate, not delete)."""
    paths.history.mkdir(parents=True, exist_ok=True)
    line = json.dumps(note.to_dict(), ensure_ascii=False)
    with (paths.history / f"{note_slug(note.note_id)}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


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
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
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
    # il retrieval_text è un campo di RICERCA, non prosa: si unisce, mai scartare
    # (la consolidazione del libro buttava i sintomi delle note assorbite e il
    # recall vago crollava da 0.625 a 0.375 di hit)
    other = existing if base is new else new
    retrieval_text = base.retrieval_text
    if other.retrieval_text and other.retrieval_text not in retrieval_text:
        retrieval_text = f"{retrieval_text} {other.retrieval_text}".strip()
    return dataclasses.replace(
        base,
        aliases=list(dict.fromkeys(existing.aliases + new.aliases)),
        tags=list(dict.fromkeys(existing.tags + new.tags)),
        retrieval_text=retrieval_text,
        relations=_dedup_relations(existing.relations + new.relations),
        proposed_links=_dedup_links(existing.proposed_links + new.proposed_links),
        sources=sources,
        confidence=max(existing.confidence, new.confidence),
    )


def write_note_json(paths: TalamusPaths, note: CanonicalNote) -> None:
    paths.notes_cache.mkdir(parents=True, exist_ok=True)
    path = paths.notes_cache / f"{note_slug(note.note_id)}.json"
    now = _now()
    if path.is_file():
        existing = _note_from_dict(json.loads(path.read_text(encoding="utf-8")))
        _append_history(paths, existing)
        note = merge_notes(existing, note)
        note = dataclasses.replace(note, created_at=existing.created_at or now, updated_at=now)
    else:
        note = dataclasses.replace(note, created_at=now, updated_at=now)
    path.write_text(json.dumps(note.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def overwrite_note_json(paths: TalamusPaths, note: CanonicalNote) -> None:
    """Replace a note (no merge); the prior version is preserved in history."""
    paths.notes_cache.mkdir(parents=True, exist_ok=True)
    path = paths.notes_cache / f"{note_slug(note.note_id)}.json"
    now = _now()
    created = note.created_at
    if path.is_file():
        existing = _note_from_dict(json.loads(path.read_text(encoding="utf-8")))
        _append_history(paths, existing)
        created = existing.created_at or now
    note = dataclasses.replace(note, created_at=created or now, updated_at=now)
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
    from talamus.indexes import build_search_index
    from talamus.ontology_lab import active_surface_map

    notes = load_notes(paths)
    paths.cache.mkdir(parents=True, exist_ok=True)
    save_graph(paths.graph_file, build_graph(notes))
    save_ontology(paths.ontology_file, build_ontology(notes, active_surface_map(paths)))
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
    build_search_index(paths, notes)  # persistent index (sqlite/FTS5 or postings)
    _write_cache_manifest(paths)


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
