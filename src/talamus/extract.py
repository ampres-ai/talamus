from __future__ import annotations

from typing import cast

from talamus.model_json import json_array
from talamus.models import CanonicalNote, ProposedLink, Relation, SourceRef
from talamus.normalize import NormalizedPackage, NormalizedSection
from talamus.routing import Router, TaskClass

# Instructions are ALWAYS English (cheap local models follow English best); the
# user-facing prose comes out in {language}; the machine layer (canonical alias,
# relation verbs, half of retrieval_text) stays English-canonical so search and
# the emergent ontology work across languages. See dev/research notes (Fase RS).
_PROMPT = """You are an expert librarian: you turn source text into clear, self-contained
knowledge NOTES. Return ONLY a JSON array, no comments. Each note = ONE reusable
concept, with these fields:
- "title": the concept's name, in {language}.
- "aliases": alternative names and acronyms (list). ALWAYS include the English
  canonical name of the concept as one alias — it powers cross-language search.
- "tags": 3-6 thematic labels (list, lowercase English).
- "summary": 1-2 sentences in {language}: what it is and why it matters
  (do NOT repeat them in the body).
- "retrieval_text": search keywords in ONE string. Include the key terms BOTH in
  {language} AND in English, so the note is findable in either language. THEN add
  3-6 SYMPTOM PHRASINGS: the colloquial words someone would actually use when they
  face the problem this note solves, WITHOUT knowing its name — in {language} AND
  English (e.g. for hallucination: "si inventa le cose, risponde cose false,
  makes things up, wrong facts"). This is what makes vague questions findable.
- "body_sections": object using ONLY these keys, when pertinent, in this order:
    "definizione"  : what it is, in connected full sentences.
    "funzionamento": how it works / how to use it, explaining WHY.
    "quando"       : when it helps and when it does not, with reasons.
    "esempio"      : an example or concrete case, if present in the source.
    "relazioni"    : how it links to or contrasts with other concepts.
  Write ALL body prose in {language}. The keys stay exactly as given (they are
  structural identifiers, not display text).
- "relations": list of {{"source","relation","target","confidence"}} toward OTHER
  mentioned concepts. Use ENGLISH verbs for "relation" (e.g. uses, is-a, part-of,
  contrasts-with, depends-on, feeds, replaces, extends): English relation surfaces
  keep the emergent ontology consistent across languages. Fill this carefully —
  it builds the knowledge map.
- "proposed_links": list of {{"anchor","target","reason"}}. "anchor" = a phrase that
  appears VERBATIM in the body at the FIRST mention of the concept, in ANY section
  (not only in "relazioni"), so the reader can click the concept right where they
  meet it. "target" = another note's title. One anchor per concept. Propose links
  only toward concepts that deserve their own note; the system discards links to
  missing notes on its own.
- "supported_claims": sentences supported by the source text (list).
- "confidence": number 0..1.

WRITING RULES (important):
- Write the notes in correct {language}, with proper accents and grammar.
- Write CONNECTED, reasoned prose, NOT telegraphic fragments. Link propositions
  ("therefore", "because", "unlike", "in practice" — in {language}).
- Every section must stand on its own for someone who never read the source.
- Clear and complete BUT concise: a few sentences per section, no filler.
- Explain the reasoning PRESENT in the source; do NOT invent unsupported facts.
- Never copy raw blocks: rewrite in your own words.

TEXT:
{text}
"""


def _extract_json_array(raw: str) -> list[dict]:
    return cast(list[dict], json_array(raw))


def _section_source(
    section: NormalizedSection,
    package: NormalizedPackage,
    claims: list[str],
    normalized_path: str,
) -> SourceRef:
    return SourceRef(
        raw_path=package.raw_path,
        normalized_path=f"{normalized_path}#section-{section.section_id}",
        locator=f"section {section.section_id}: {section.title}",
        source_hash=package.source_hash,
        supported_claims=claims,
    )


def extract_notes(
    package: NormalizedPackage,
    router: Router,
    normalized_path: str | None = None,
    preamble: str = "",
    language: str = "English",
    task: TaskClass = TaskClass.EXTRACTION,
) -> list[CanonicalNote]:
    """Extract concept notes. ``preamble`` prepends extra instructions to the
    librarian prompt (e.g. the code-aware variant used by repo scans);
    ``language`` is the user's reading language for the note prose. ``task`` lets
    callers with a different intent than bulk extraction (e.g. remembering a single
    agent session) request their own tier — see talamus.routing.TaskClass."""
    norm = normalized_path or package.raw_path
    text = "\n\n".join(f"# {s.title}\n{s.text}" for s in package.sections)
    llm = router.for_task(task)
    raw = llm.complete(preamble + _PROMPT.format(text=text, language=language))
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
            sources=[_section_source(primary_section, package, claims, norm)],
            confidence=float(candidate.get("confidence", 0.8)),
        )
        notes.append(note)
    return notes
