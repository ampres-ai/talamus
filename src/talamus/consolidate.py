"""Concept consolidation: merge near-duplicate concept notes.

The same concept often gets two notes under different names or languages
(e.g. "Hybrid search" and "Ricerca ibrida"). An LLM groups true synonyms from the
title+summary list; merging folds the duplicates into one canonical note.
"""

from __future__ import annotations

import dataclasses
import json

from talamus.linking import NoteRegistry
from talamus.model_json import balanced_objects
from talamus.models import CanonicalNote, Relation
from talamus.naming import note_filename, note_slug
from talamus.paths import TalamusPaths
from talamus.routing import Router, TaskClass
from talamus.store import (
    load_notes,
    merge_notes,
    rebuild_indexes,
    render_note_markdown,
)

# English instructions (three-layer language rule); titles are echoed verbatim.
_PROMPT = """You are a librarian. Below is a list of NOTES (id, title: summary).
Find the groups of notes that describe the EXACT same concept, even under
different names or languages (e.g. "Hybrid search" and "Ricerca ibrida" are the
same concept; "Fine-tuning" and "Finetuning" too). Do NOT group concepts that are
merely related or similar: only true synonyms, spelling variants, or translations
of the same concept.

Return ONLY a JSON array of groups; each group:
{"canonical": "<title to keep>", "members": ["<title>", "<title>", ...]}
Echo the titles EXACTLY as written. Only include groups with 2 or more members.
If there are no duplicates, return [].

NOTES:
__NOTES__
"""


def _dedup_relations(relations: list[Relation]) -> list[Relation]:
    seen: set[tuple[str, str, str]] = set()
    out: list[Relation] = []
    for relation in relations:
        key = (relation.source, relation.relation, relation.target)
        if key not in seen:
            seen.add(key)
            out.append(relation)
    return out


def _detect_groups(notes: list[CanonicalNote], router: Router) -> list[dict]:
    if len(notes) < 2:
        return []
    listing = "\n".join(f"- [{n.note_id}] {n.title}: {n.summary}" for n in notes)
    llm = router.for_task(TaskClass.CONSOLIDATE)
    raw = llm.complete(_PROMPT.replace("__NOTES__", listing))
    parsed = balanced_objects(raw)
    titles = {n.title for n in notes}
    groups: list[dict] = []
    for group in parsed:
        if not isinstance(group, dict):
            continue
        members = list(dict.fromkeys(m for m in group.get("members", []) if m in titles))
        if len(members) < 2:
            continue
        canonical = group.get("canonical")
        if canonical not in members:
            canonical = members[0]
        groups.append({"canonical": canonical, "members": members})
    return groups


def find_duplicates(paths: TalamusPaths, router: Router) -> list[dict]:
    """Return the proposed merge groups (does not change anything)."""
    return _detect_groups(load_notes(paths), router)


def apply_consolidation(
    paths: TalamusPaths, router: Router, groups: list[dict] | None = None
) -> int:
    """Merge duplicate groups. Returns how many notes were merged away.

    ``groups`` lets the caller pass REVIEWED groups (the model sometimes lumps
    related-but-distinct concepts, e.g. Perplexity with Cross-Entropy on the
    book brain): detection proposes, a human or a filter decides."""
    notes = load_notes(paths)
    if groups is None:
        groups = _detect_groups(notes, router)
    if not groups:
        return 0

    by_title: dict[str, CanonicalNote] = {n.title: n for n in notes}
    removed: dict[str, CanonicalNote] = {}
    to_canonical: dict[str, str] = {}
    merged_count = 0

    for group in groups:
        canonical_title = group["canonical"]
        canonical = by_title.get(canonical_title)
        if canonical is None:
            continue
        for member_title in group["members"]:
            member = by_title.get(member_title)
            if member_title == canonical_title or member is None or member_title in removed:
                continue
            with_alias = dataclasses.replace(member, aliases=[*member.aliases, member.title])
            merged = merge_notes(canonical, with_alias)
            aliases = [
                a for a in dict.fromkeys([*merged.aliases, member.title]) if a != canonical_title
            ]
            canonical = dataclasses.replace(
                merged, note_id=canonical.note_id, title=canonical_title, aliases=aliases
            )
            removed[member_title] = member
            to_canonical[member_title] = canonical_title
            merged_count += 1
        by_title[canonical_title] = canonical

    if merged_count == 0:
        return 0

    for member in removed.values():
        (paths.notes_cache / f"{note_slug(member.note_id)}.json").unlink(missing_ok=True)
        (paths.notes / note_filename(member.title)).unlink(missing_ok=True)

    survivors: list[CanonicalNote] = []
    for title, note in by_title.items():
        if title in removed:
            continue
        relations = _dedup_relations(
            [
                dataclasses.replace(r, target=to_canonical.get(r.target, r.target))
                for r in note.relations
            ]
        )
        survivors.append(dataclasses.replace(note, relations=relations))

    for note in survivors:
        (paths.notes_cache / f"{note_slug(note.note_id)}.json").write_text(
            json.dumps(note.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
    registry = NoteRegistry.from_notes(survivors)
    for note in survivors:
        render_note_markdown(paths, note, registry)
    rebuild_indexes(paths)
    return merged_count
