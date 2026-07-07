"""Symptom enrichment: the semantic bridge for vague questions (RS2.4-bis).

"The model makes things up" shares no token with the note "Hallucination": the gap
is purely semantic and no query-time trick closes it (PRF and triangulation rejected
with data). The by-construction cure: add to the ``retrieval_text`` the symptom
phrasings a user would use to pose the problem without knowing its name — paid ONCE,
in batches, on an already-existing brain.

Kept separate from extraction on purpose: loading the extraction prompt with the
symptom directive was measured (A/B re-ingest of the book) and costs coverage on
lite models (-12% notes, more malformed JSON). Here the batches are small, the
output echoes only ids, and one malformed batch does not touch the others.
"""

from __future__ import annotations

import dataclasses
import json

from talamus.model_json import json_array
from talamus.paths import TalamusPaths
from talamus.routing import Router, TaskClass
from talamus.store import load_notes, overwrite_note_json, rebuild_indexes

BATCH_SIZE = 20
_MARKER = " ~symptoms: "  # separates symptoms in retrieval_text and makes enrich idempotent

_PROMPT = """You are a search-quality engineer. For each NOTE below, write the SYMPTOM
PHRASINGS: the colloquial words someone would actually use when they face the
problem the note solves, WITHOUT knowing its name. 2-4 short phrases per note,
in {language} AND in English (e.g. for hallucination: "si inventa le cose,
risponde cose false, makes things up, wrong facts").

Use the note's definition and details (not just its name) to find the symptoms
a user would actually describe.

Return ONLY a JSON array, echoing the note id:
[{{"id": "<note id>", "symptoms": "<phrases separated by commas>"}}]

NOTES (id | title — summary — details):
{notes}
"""

_BODY_CHARS = 360  # how much body to give the model to infer the symptoms


def _note_brief(note) -> str:
    """id, title, summary and an extract of the BODY: symptoms inferred from the body
    (not from the summary alone) capture more ways of describing the problem."""
    body = " ".join(str(v) for v in note.body_sections.values()).strip()
    body = body[:_BODY_CHARS]
    return f"- {note.note_id} | {note.title} — {note.summary} — {body}"


def enrich_estimate(paths: TalamusPaths) -> dict:
    """Cost preview: notes to enrich and LLM calls. No writes."""
    pending = [n for n in load_notes(paths) if _MARKER not in n.retrieval_text]
    batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    return {"notes": len(pending), "batches": batches, "est_llm_calls": batches}


def enrich_notes(paths: TalamusPaths, router: Router, language: str = "English") -> dict:
    """Add the symptom phrasings to the retrieval_text of notes that lack them.

    Idempotent (marker in retrieval_text); a malformed batch is skipped and counted,
    without touching the others. Reindexes once at the end."""
    notes = [n for n in load_notes(paths) if _MARKER not in n.retrieval_text]
    by_id = {n.note_id: n for n in notes}
    enriched = 0
    failed_batches = 0
    llm = router.for_task(TaskClass.ENRICH)
    for offset in range(0, len(notes), BATCH_SIZE):
        batch = notes[offset : offset + BATCH_SIZE]
        listing = "\n".join(_note_brief(n) for n in batch)
        raw = llm.complete(_PROMPT.format(language=language, notes=listing))
        try:
            parsed = json_array(raw)
        except (ValueError, json.JSONDecodeError):
            failed_batches += 1
            continue
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            note = by_id.get(str(entry.get("id", "")))
            symptoms = str(entry.get("symptoms", "")).strip()
            if note is None or not symptoms or _MARKER in note.retrieval_text:
                continue
            # guard-rail for weak models: the retrieval_text must not be polluted
            if len(symptoms) > 400 or any(c in symptoms for c in "{}[]<>"):
                continue
            updated = dataclasses.replace(
                note, retrieval_text=f"{note.retrieval_text}{_MARKER}{symptoms}"
            )
            # overwrite, not merge: write_note_json at equal confidence would keep the old text
            overwrite_note_json(paths, updated)
            enriched += 1
    if enriched:
        rebuild_indexes(paths)
    return {
        "enriched": enriched,
        "skipped": len(notes) - enriched,
        "failed_batches": failed_batches,
    }
