from __future__ import annotations

import json

from kortex.adapters.llm import LLMProvider
from kortex.models import CanonicalNote, Relation, SourceRef
from kortex.normalize import NormalizedPackage, NormalizedSection

_PROMPT = """Sei un estrattore di conoscenza. Leggi il testo e produci un ARRAY JSON di note.
Ogni nota e un concetto riutilizzabile con i campi:
title, aliases (lista), tags (lista), summary, retrieval_text,
body_sections (oggetto sezione->testo), relations (lista di {{source,relation,target,confidence}}),
supported_claims (lista di frasi sostenute dal testo), confidence (0..1).
Rispondi SOLO con l'array JSON, senza commenti.

TESTO:
{text}
"""


def _extract_json_array(raw: str) -> list[dict]:
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("nessun array JSON nella risposta del modello")
    return json.loads(raw[start : end + 1])


def _section_source(section: NormalizedSection, package: NormalizedPackage, claims: list[str]) -> SourceRef:
    return SourceRef(
        raw_path=package.raw_path,
        normalized_path=f"{package.raw_path}#section-{section.section_id}",
        locator=f"section {section.section_id}: {section.title}",
        source_hash=package.source_hash,
        supported_claims=claims,
    )


def extract_notes(package: NormalizedPackage, llm: LLMProvider) -> list[CanonicalNote]:
    text = "\n\n".join(f"# {s.title}\n{s.text}" for s in package.sections)
    raw = llm.complete(_PROMPT.format(text=text))
    candidates = _extract_json_array(raw)
    primary_section = package.sections[0]
    notes: list[CanonicalNote] = []
    for candidate in candidates:
        title = str(candidate.get("title", "")).strip()
        if not title:
            continue
        relations = [
            Relation(
                source=str(r.get("source", title)),
                relation=str(r.get("relation", "related")),
                target=str(r.get("target", "")),
                confidence=float(r.get("confidence", 0.5)),
            )
            for r in candidate.get("relations", [])
            if str(r.get("target", "")).strip()
        ]
        claims = [str(c) for c in candidate.get("supported_claims", [])]
        summary = str(candidate.get("summary", f"{title}."))
        body_sections = {str(k): str(v) for k, v in candidate.get("body_sections", {}).items()}
        if not body_sections:
            body_sections = {"summary": summary}
        note = CanonicalNote(
            note_id=title.lower().replace(" ", "-"),
            title=title,
            aliases=[str(a) for a in candidate.get("aliases", [])],
            folder=str(candidate.get("folder", "")),
            tags=[str(t) for t in candidate.get("tags", [])],
            summary=summary,
            retrieval_text=str(candidate.get("retrieval_text", title)),
            body_sections=body_sections,
            proposed_links=[],
            relations=relations,
            sources=[_section_source(primary_section, package, claims)],
            confidence=float(candidate.get("confidence", 0.8)),
        )
        notes.append(note)
    return notes
