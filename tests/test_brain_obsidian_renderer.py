import unittest

from brain.linking import NoteRegistry, resolve_links
from brain.models import CanonicalNote, ProposedLink, SourceRef
from brain.storage.obsidian import render_obsidian_note


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
            proposed_links=[ProposedLink(anchor="RAG", target="RAG", reason="RAG is a memory pattern.")],
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
            proposed_links=[ProposedLink(anchor="RAG", target="Retrieval-Augmented Generation", reason="RAG is relevant.")],
            relations=[],
            sources=[source_ref()],
            confidence=0.9,
        )
        registry = NoteRegistry.from_notes([note, CanonicalNote.minimal("Retrieval-Augmented Generation", sources=[source_ref()])])

        markdown = render_obsidian_note(note, registry)

        self.assertIn("aliases:", markdown)
        self.assertIn("Memory for Agents", markdown)
        self.assertIn("sources:", markdown)
        self.assertIn("## Core Idea", markdown)
        self.assertIn("[[Retrieval-Augmented Generation|RAG]]", markdown)


if __name__ == "__main__":
    unittest.main()
