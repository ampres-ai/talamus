"""Arricchimento sintomi: il ponte semantico per le domande vaghe (RS2.4-bis).

"Il modello si inventa le cose" non condivide alcun token con la nota
"Allucinazione": il gap è semantico puro e nessun trucco a query-time lo colma
(PRF e triangolazione bocciati coi dati). La cura by-construction: aggiungere al
``retrieval_text`` le frasi-sintomo con cui un utente porrebbe il problema senza
conoscerne il nome — pagate UNA volta, in lotti, su un brain già esistente.

Separato dall'estrazione di proposito: caricare il prompt di estrazione con la
direttiva sintomi è stato misurato (re-ingest A/B del libro) e costa copertura
ai modelli lite (-12% note, più JSON malformati). Qui i lotti sono piccoli,
l'output echeggia solo id, e un lotto malformato non tocca gli altri.
"""

from __future__ import annotations

import dataclasses
import json

from talamus.adapters.llm import LLMProvider
from talamus.paths import TalamusPaths
from talamus.store import load_notes, overwrite_note_json, rebuild_indexes

BATCH_SIZE = 20
_MARKER = " ~sintomi: "  # separa i sintomi nel retrieval_text e rende l'enrich idempotente

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

_BODY_CHARS = 360  # quanto corpo dare al modello per inferire i sintomi


def _note_brief(note) -> str:
    """id, titolo, summary e un estratto del CORPO: i sintomi inferiti dal corpo
    (non dal solo summary) catturano piu' modi di descrivere il problema."""
    body = " ".join(str(v) for v in note.body_sections.values()).strip()
    body = body[:_BODY_CHARS]
    return f"- {note.note_id} | {note.title} — {note.summary} — {body}"


def enrich_estimate(paths: TalamusPaths) -> dict:
    """Anteprima costi: note da arricchire e chiamate LLM. Nessuna scrittura."""
    pending = [n for n in load_notes(paths) if _MARKER not in n.retrieval_text]
    batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    return {"notes": len(pending), "batches": batches, "est_llm_calls": batches}


def enrich_notes(paths: TalamusPaths, llm: LLMProvider, language: str = "English") -> dict:
    """Aggiunge le frasi-sintomo al retrieval_text delle note che non le hanno.

    Idempotente (marker nel retrieval_text); un lotto malformato viene saltato e
    conteggiato, senza toccare gli altri. Reindicizza una volta alla fine."""
    notes = [n for n in load_notes(paths) if _MARKER not in n.retrieval_text]
    by_id = {n.note_id: n for n in notes}
    enriched = 0
    failed_batches = 0
    for offset in range(0, len(notes), BATCH_SIZE):
        batch = notes[offset : offset + BATCH_SIZE]
        listing = "\n".join(_note_brief(n) for n in batch)
        raw = llm.complete(_PROMPT.format(language=language, notes=listing))
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end == -1 or end <= start:
            failed_batches += 1
            continue
        try:
            parsed = json.loads(raw[start : end + 1], strict=False)
        except json.JSONDecodeError:
            failed_batches += 1
            continue
        for entry in parsed if isinstance(parsed, list) else []:
            if not isinstance(entry, dict):
                continue
            note = by_id.get(str(entry.get("id", "")))
            symptoms = str(entry.get("symptoms", "")).strip()
            if note is None or not symptoms or _MARKER in note.retrieval_text:
                continue
            # guard-rail per modelli deboli: il retrieval_text non va inquinato
            if len(symptoms) > 400 or any(c in symptoms for c in "{}[]<>"):
                continue
            updated = dataclasses.replace(
                note, retrieval_text=f"{note.retrieval_text}{_MARKER}{symptoms}"
            )
            # overwrite, non merge: write_note_json a pari confidence terrebbe il vecchio testo
            overwrite_note_json(paths, updated)
            enriched += 1
    if enriched:
        rebuild_indexes(paths)
    return {
        "enriched": enriched,
        "skipped": len(notes) - enriched,
        "failed_batches": failed_batches,
    }
