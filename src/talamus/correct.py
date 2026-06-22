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

_PROMPT = """Here is a NOTE and its SOURCE. Is the note faithful to the source?
If it is faithful, reply ONLY with: {"ok": true}
If it is NOT faithful (errors, or claims invented beyond the source), reply ONLY with:
{"ok": false, "summary": "<corrected summary>", "body": "<corrected definition>"}
based SOLELY on the source. Write the corrected text in the SAME LANGUAGE as the note.

NOTE
title: <TITLE>
summary: <SUMMARY>
body: <BODY>

SOURCE
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


def _write_correction(paths: TalamusPaths, note: CanonicalNote, summary: str, body: str) -> None:
    """Write a corrected note: history preserved, indexes rebuilt, claims rolled (F7.4)."""
    body_sections = dict(note.body_sections)
    if body:
        body_sections["definizione"] = str(body)
    corrected = dataclasses.replace(
        note,
        summary=summary or note.summary,
        body_sections=body_sections,
    )
    overwrite_note_json(paths, corrected)
    render_note_markdown(paths, corrected, NoteRegistry.from_notes(load_notes(paths)))
    rebuild_indexes(paths)
    _record_correction_claims(paths, note, corrected)


def apply_correction(paths: TalamusPaths, title: str, llm: LLMProvider) -> bool:
    """Verify and, if needed, write the corrected note (old version kept in history)."""
    result = verify_note(paths, title, llm)
    if not result.get("found") or result.get("ok", True):
        return False
    note = _find(load_notes(paths), title)
    if note is None:
        return False
    _write_correction(
        paths, note, str(result.get("summary", note.summary)), str(result.get("body", ""))
    )
    return True


def apply_proposed_correction(paths: TalamusPaths, detail: dict) -> bool:
    """Apply a correction previously parked in the review queue (F7.3)."""
    note = _find(load_notes(paths), str(detail.get("title", "")))
    if note is None:
        return False
    _write_correction(paths, note, str(detail.get("summary", "")), str(detail.get("body", "")))
    return True


LOW_CONFIDENCE = 0.5


def _resolve_source(paths: TalamusPaths, note: CanonicalNote):
    """Prefer the RAW file: source_hash was computed on its extracted text.
    The normalized view is derived (different bytes) and only proves existence."""
    for source in note.sources:
        rel = source.normalized_path.split("#")[0]
        for candidate in (paths.project_root / source.raw_path, paths.project_root / rel):
            if candidate.is_file():
                return source, candidate
    return None, None


def _extracted_hash(path) -> str:
    """Hash of the re-extracted TEXT (the same artifact the ingest hashed):
    comparing raw file bytes breaks on Windows newlines and binary sources."""
    import hashlib

    from talamus.sources import extract_text

    return hashlib.sha256(extract_text(path).encode("utf-8")).hexdigest()


def provenance_status(paths: TalamusPaths, note: CanonicalNote) -> dict:
    """Deterministic provenance health of one note (F7.2). No LLM."""
    status = "ok"
    detail = ""
    source, resolved = _resolve_source(paths, note)
    if not note.sources:
        status, detail = "source_missing", "the note has no recorded sources"
    elif resolved is None:
        status = "source_missing"
        detail = f"source not found: {note.sources[0].normalized_path}"
    else:
        stored = source.source_hash.removeprefix("sha256:")
        is_raw = resolved == paths.project_root / source.raw_path
        if is_raw and len(stored) >= 16 and all(c in "0123456789abcdef" for c in stored):
            try:
                current = _extracted_hash(resolved)
            except Exception:
                status = "source_missing"
                detail = f"unreadable source: {resolved.name}"
            else:
                if not current.startswith(stored[: len(current)]) and not stored.startswith(
                    current[: len(stored)]
                ):
                    status = "source_changed"
                    detail = f"the source {resolved.name} changed after extraction"
    if status == "ok" and note.confidence < LOW_CONFIDENCE:
        status, detail = "low_confidence", f"extraction confidence {note.confidence}"
    return {"note_id": note.note_id, "title": note.title, "status": status, "detail": detail}


def provenance_report(paths: TalamusPaths) -> list[dict]:
    return [provenance_status(paths, note) for note in load_notes(paths)]


def verify_batch(
    paths: TalamusPaths,
    llm: LLMProvider,
    only_stale: bool = False,
    source_filter: str | None = None,
) -> dict:
    """Batch verification (F7.1): stale provenance becomes review items without
    LLM cost; content checks propose corrections to the review queue — uncertain
    changes never overwrite notes directly."""
    from talamus.review import ReviewQueue

    queue = ReviewQueue(paths)
    report = {"checked": 0, "ok": 0, "stale": 0, "corrections_proposed": 0, "skipped": 0}
    for note in load_notes(paths):
        if source_filter and not any(
            source_filter in s.normalized_path or source_filter in s.raw_path for s in note.sources
        ):
            report["skipped"] += 1
            continue
        health = provenance_status(paths, note)
        if health["status"] != "ok":
            report["stale"] += 1
            queue.add(
                "stale_source",
                f"{note.title}: {health['status']}",
                {"title": note.title, **health},
            )
            continue
        if only_stale:
            report["skipped"] += 1
            continue
        result = verify_note(paths, note.title, llm)
        report["checked"] += 1
        if result.get("ok", True):
            report["ok"] += 1
            continue
        report["corrections_proposed"] += 1
        queue.add(
            "correction",
            f"{note.title}: the note does not match the source",
            {
                "title": note.title,
                "summary": str(result.get("summary", "")),
                "body": str(result.get("body", "")),
            },
        )
    return report


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
