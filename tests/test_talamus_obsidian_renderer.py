import unittest

from talamus.linking import NoteRegistry, resolve_links
from talamus.models import CanonicalNote, ProposedLink, SourceRef
from talamus.storage.obsidian import render_obsidian_note


def source_ref() -> SourceRef:
    return SourceRef(
        raw_path="knowledge/raw/pdf/book.pdf",
        normalized_path="knowledge/normalized/pdf/book/sections/001.md",
        locator="pages 1-2",
        source_hash="sha256:abc",
        supported_claims=["RAG retrieves context."],
    )


class ObsidianRendererTests(unittest.TestCase):
    def test_same_batch_alias_link_resolves(self) -> None:
        rag = CanonicalNote.minimal("Retrieval-Augmented Generation", sources=[source_ref()])
        dependent = CanonicalNote(
            note_id="agent-memory",
            title="Agent Memory",
            aliases=[],
            folder="Agents",
            tags=["agents"],
            summary="Agent memory stores useful context.",
            retrieval_text="agent memory rag retrieval",
            body_sections={"core_idea": "Agent memory can use RAG."},
            proposed_links=[
                ProposedLink(anchor="RAG", target="RAG", reason="RAG is a memory pattern.")
            ],
            relations=[],
            sources=[source_ref()],
            confidence=0.9,
        )
        registry = NoteRegistry.from_notes([rag, dependent], extra_aliases={"RAG": rag.title})

        resolved = resolve_links(dependent, registry)

        self.assertEqual("[[Retrieval-Augmented Generation|RAG]]", resolved["RAG"])

    def test_renderer_includes_frontmatter_sources_and_body_link(self) -> None:
        note = CanonicalNote(
            note_id="agent-memory",
            title="Agent Memory",
            aliases=["Memory for Agents"],
            folder="Agents",
            tags=["agents"],
            summary="Agent memory stores useful context.",
            retrieval_text="agent memory rag retrieval",
            body_sections={"core_idea": "Agent memory can use RAG."},
            proposed_links=[
                ProposedLink(
                    anchor="RAG", target="Retrieval-Augmented Generation", reason="RAG is relevant."
                )
            ],
            relations=[],
            sources=[source_ref()],
            confidence=0.9,
        )
        registry = NoteRegistry.from_notes(
            [note, CanonicalNote.minimal("Retrieval-Augmented Generation", sources=[source_ref()])]
        )

        markdown = render_obsidian_note(note, registry)

        self.assertIn("aliases:", markdown)
        self.assertIn("Memory for Agents", markdown)
        self.assertIn("sources:", markdown)
        self.assertIn("## Core Idea", markdown)
        self.assertIn("[[Retrieval-Augmented Generation|RAG]]", markdown)

    def test_self_links_are_dropped(self) -> None:
        """Real-world flaw from the book pilot: the model proposes links whose
        target is the note itself (directly or via alias) — never render them."""
        note = CanonicalNote(
            note_id="perplessità",
            title="Perplessità",
            aliases=["Perplexity"],
            folder="",
            tags=[],
            summary="Esponenziale della cross entropy.",
            retrieval_text="perplessità perplexity",
            body_sections={"definizione": "Metrica che quantifica l'incertezza."},
            proposed_links=[
                ProposedLink(anchor="quantifica l'incertezza", target="Perplessità", reason="self"),
                ProposedLink(anchor="PPL", target="Perplexity", reason="self via alias"),
                ProposedLink(anchor="Cross Entropy", target="Cross Entropy", reason="real"),
            ],
            relations=[],
            sources=[source_ref()],
            confidence=0.9,
        )
        registry = NoteRegistry.from_notes(
            [note, CanonicalNote.minimal("Cross Entropy", sources=[source_ref()])]
        )

        resolved = resolve_links(note, registry)

        self.assertEqual(["Cross Entropy"], list(resolved))
        markdown = render_obsidian_note(note, registry)
        self.assertNotIn("[[Perplessità", markdown)

    def test_body_link_applied_once_across_sections(self) -> None:
        note = CanonicalNote(
            note_id="rag",
            title="RAG",
            aliases=[],
            folder="",
            tags=[],
            summary="RAG.",
            retrieval_text="rag",
            body_sections={
                "definizione": "Usa un Vector Store.",
                "relazioni": "Si appoggia al Vector Store.",
            },
            proposed_links=[
                ProposedLink(anchor="Vector Store", target="Vector Store", reason="infra")
            ],
            relations=[],
            sources=[source_ref()],
            confidence=0.9,
        )
        registry = NoteRegistry.from_notes(
            [note, CanonicalNote.minimal("Vector Store", sources=[source_ref()])]
        )

        markdown = render_obsidian_note(note, registry)

        body = markdown.split("## Related")[0]
        self.assertEqual(1, body.count("[[Vector Store|Vector Store]]"))


if __name__ == "__main__":
    unittest.main()
