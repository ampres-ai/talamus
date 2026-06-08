from __future__ import annotations

import json

from talamus.adapters.llm import LLMProvider
from talamus.models import CanonicalNote, ProposedLink, Relation, SourceRef
from talamus.normalize import NormalizedPackage, NormalizedSection

_PROMPT = """Sei un bibliotecario esperto: trasformi il testo in SCHEDE di conoscenza chiare e
autosufficienti. Restituisci SOLO un ARRAY JSON, senza commenti. Ogni scheda = UN
concetto riutilizzabile, con questi campi:
- "title": il nome del concetto.
- "aliases": nomi alternativi e sigle (lista).
- "tags": 3-6 etichette tematiche (lista).
- "summary": 1-2 frasi che dicono in sintesi cos'è e perché conta (NON ripeterlo nel corpo).
- "retrieval_text": parole chiave e termini di ricerca, in una sola stringa.
- "body_sections": oggetto che usa SOLO queste chiavi, quando pertinenti, in quest'ordine:
    "definizione"  : cos'è, in frasi complete e collegate.
    "funzionamento": come funziona / come si usa, spiegando il PERCHÉ.
    "quando"       : quando conviene e quando no, motivando.
    "esempio"      : un esempio o caso concreto, se presente nella fonte.
    "relazioni"    : come si lega o si contrappone ad altri concetti
                     ("a differenza di...", "usa...", "è un tipo di...").
- "relations": lista di {{"source","relation","target","confidence"}} verso ALTRI
  concetti citati (es. uses, is-a, contrasts-with, part-of). Compilala con cura:
  serve a costruire la mappa della conoscenza.
- "proposed_links": lista di {{"anchor","target","reason"}}. "anchor" = una frase che
  compare LETTERALMENTE nel corpo, alla PRIMA menzione del concetto, in QUALSIASI
  sezione (Definizione, Funzionamento, ecc.) e non solo in "relazioni": così il
  lettore puo cliccare il concetto proprio dove lo incontra. "target" = il titolo di
  un'altra scheda. Una sola ancora per concetto. Proponi link solo verso concetti che
  meritano una scheda propria; il sistema scarta da solo i link verso schede inesistenti.
- "supported_claims": frasi sostenute dal testo (lista).
- "confidence": numero 0..1.

REGOLE DI SCRITTURA (importanti):
- Scrivi in italiano corretto e con gli accenti giusti (è, é, perché, può, così, già).
- Scrivi PROSA connessa e ragionata, NON frammenti o elenchi telegrafici. Collega le
  proposizioni ("quindi", "perché", "a differenza di", "in pratica").
- Ogni sezione deve poter essere capita da sola, da chi non ha letto la fonte.
- Chiaro e completo MA conciso: poche frasi per sezione, nessun riempitivo.
- Spiega il ragionamento PRESENTE nella fonte; NON inventare fatti non supportati.
- Non copiare blocchi grezzi: rielabora con parole tue.

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
        proposed = [
            ProposedLink(
                anchor=str(p.get("anchor", "")),
                target=str(p.get("target", "")),
                reason=str(p.get("reason", "")),
            )
            for p in candidate.get("proposed_links", [])
            if str(p.get("anchor", "")).strip() and str(p.get("target", "")).strip()
        ]
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
            proposed_links=proposed,
            relations=relations,
            sources=[_section_source(primary_section, package, claims)],
            confidence=float(candidate.get("confidence", 0.8)),
        )
        notes.append(note)
    return notes
