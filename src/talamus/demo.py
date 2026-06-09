"""A small, LLM-free example brain so users can try Talamus instantly."""

from __future__ import annotations

from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote, Relation, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import load_notes, rebuild_indexes, render_note_markdown, write_note_json


def _note(title: str, summary: str, body: str, relations: list[tuple[str, str]]) -> CanonicalNote:
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=[],
        folder="",
        tags=["demo"],
        summary=summary,
        retrieval_text=title.lower(),
        body_sections={"definizione": body},
        proposed_links=[],
        relations=[
            Relation(source=title, relation=rel, target=target, confidence=0.9)
            for rel, target in relations
        ],
        sources=[SourceRef("demo", "demo", "demo", "sha256:demo", [summary])],
        confidence=0.9,
    )


def _demo_notes() -> list[CanonicalNote]:
    return [
        _note(
            "Retrieval-Augmented Generation",
            "Architettura che fornisce a un LLM del contesto recuperato da una base esterna.",
            "La RAG recupera i documenti pertinenti e li passa al modello come contesto, "
            "così la risposta può citare fonti aggiornate senza riaddestrare il modello.",
            [("uses", "Embedding"), ("uses", "Reranking")],
        ),
        _note(
            "Embedding",
            "Rappresentazione vettoriale del significato di un testo.",
            "Un embedding mappa il testo in un vettore numerico dove i significati simili "
            "stanno vicini; è il mattone della ricerca semantica.",
            [("part-of", "Retrieval-Augmented Generation")],
        ),
        _note(
            "Reranking",
            "Secondo stadio del recupero che riordina i candidati per pertinenza.",
            "Il reranking riordina i risultati grezzi del recupero per portare in cima i più "
            "pertinenti alla domanda, migliorando il contesto passato al modello.",
            [("part-of", "Retrieval-Augmented Generation")],
        ),
    ]


def create_demo_brain(paths: TalamusPaths) -> int:
    """Write a few pre-baked, cross-linked notes and build the indexes. Returns the note count."""
    paths.ensure_directories()
    notes = _demo_notes()
    for note in notes:
        write_note_json(paths, note)
    registry = NoteRegistry.from_notes(load_notes(paths))
    for note in notes:
        render_note_markdown(paths, note, registry)
    rebuild_indexes(paths)
    return len(notes)
