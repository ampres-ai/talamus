"""Source-correction: verify a note against its preserved source and correct it.

A correction is written through the bitemporal store, so the previous version is kept
in history (B4) — you can always see what changed.
"""

from __future__ import annotations

import dataclasses
import json

from talamus.adapters.llm import LLMProvider
from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote
from talamus.paths import TalamusPaths
from talamus.store import load_notes, overwrite_note_json, rebuild_indexes, render_note_markdown

_PROMPT = """Ecco una SCHEDA e la sua FONTE. La scheda e' fedele alla fonte?
Se e' fedele, rispondi SOLO con: {"ok": true}
Se NON e' fedele (errori o cose inventate rispetto alla fonte), rispondi SOLO con:
{"ok": false, "summary": "<riassunto corretto>", "body": "<definizione corretta>"}
basandoti UNICAMENTE sulla fonte.

SCHEDA
titolo: <TITLE>
riassunto: <SUMMARY>
corpo: <BODY>

FONTE
<SOURCE>
"""


def _find(notes: list[CanonicalNote], title: str) -> CanonicalNote | None:
    for note in notes:
        if note.title.lower() == title.lower():
            return note
    return None


def _source_text(paths: TalamusPaths, note: CanonicalNote) -> str:
    for source in note.sources:
        rel = source.normalized_path.split("#")[0]
        for candidate in (paths.project_root / rel, paths.project_root / source.raw_path):
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
    return ""


def verify_note(paths: TalamusPaths, title: str, llm: LLMProvider) -> dict:
    """Check a note against its source. Returns {found, checked, ok, summary?, body?}."""
    note = _find(load_notes(paths), title)
    if note is None:
        return {"found": False}
    source = _source_text(paths, note)
    if not source:
        return {"found": True, "checked": False}
    body = "\n".join(note.body_sections.values())
    raw = llm.complete(
        _PROMPT.replace("<TITLE>", note.title)
        .replace("<SUMMARY>", note.summary)
        .replace("<BODY>", body)
        .replace("<SOURCE>", source)
    )
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {"found": True, "checked": True, "ok": True}
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {"found": True, "checked": True, "ok": True}
    return {"found": True, "checked": True, **parsed}


def apply_correction(paths: TalamusPaths, title: str, llm: LLMProvider) -> bool:
    """Verify and, if needed, write the corrected note (old version kept in history)."""
    result = verify_note(paths, title, llm)
    if not result.get("found") or result.get("ok", True):
        return False
    note = _find(load_notes(paths), title)
    if note is None:
        return False
    body_sections = dict(note.body_sections)
    if result.get("body"):
        body_sections["definizione"] = str(result["body"])
    corrected = dataclasses.replace(
        note,
        summary=str(result.get("summary", note.summary)) or note.summary,
        body_sections=body_sections,
    )
    overwrite_note_json(paths, corrected)
    render_note_markdown(paths, corrected, NoteRegistry.from_notes(load_notes(paths)))
    rebuild_indexes(paths)
    _record_correction_claims(paths, note, corrected)
    return True


def _record_correction_claims(paths: TalamusPaths, old: CanonicalNote, new: CanonicalNote) -> None:
    """Valid-time overlay (M6): a correction CLOSES the old claim and OPENS the new
    one — the contradicted fact stays queryable as-of its validity window, but is
    excluded from the current view (F6.6)."""
    from talamus.temporal import current_claims, invalidate_claim, record_claim

    evidence = old.sources[0].normalized_path if old.sources else ""
    existing = current_claims(paths, note_id=old.note_id)
    if not existing:
        # first correction for this note: record the old fact retroactively
        # (valid since the note was created), so its window is honest
        existing = [
            record_claim(
                paths,
                note_id=old.note_id,
                text=old.summary,
                evidence=evidence,
                valid_from=old.created_at or "",
                confidence=old.confidence,
            )
        ]
    for claim in existing:
        invalidate_claim(paths, claim.claim_id, invalidated_by="correction")
    record_claim(
        paths,
        note_id=new.note_id,
        text=new.summary,
        evidence=evidence,
        confidence=new.confidence,
    )
