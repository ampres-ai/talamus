import unittest

from kortex.linking import NoteRegistry
from kortex.models import CanonicalNote, SourceRef
from kortex.noteparse import parse_note_markdown
from kortex.storage.obsidian import render_obsidian_note


def _note() -> CanonicalNote:
    return CanonicalNote(
        note_id="agent-memory",
        title="Agent Memory",
        aliases=["Memory for Agents"],
        folder="Agents",
        tags=["agents", "memory"],
        summary="Agent memory stores useful context.",
        retrieval_text="agent memory rag",
        body_sections={"core_idea": "Agent memory can use RAG."},
        proposed_links=[],
        relations=[],
        sources=[SourceRef("raw/a.md", "norm/a#1", "section 1", "sha256:x", ["claim"])],
        confidence=0.9,
    )


class NoteParseTests(unittest.TestCase):
    def test_parse_extracts_human_fields_from_rendered_note(self) -> None:
        note = _note()
        markdown = render_obsidian_note(note, NoteRegistry.from_notes([note]))

        parsed = parse_note_markdown(markdown)

        self.assertEqual("agent-memory", parsed["id"])
        self.assertEqual("Agent Memory", parsed["title"])
        self.assertEqual(["Memory for Agents"], parsed["aliases"])
        self.assertEqual(["agents", "memory"], parsed["tags"])
        self.assertEqual("Agent memory stores useful context.", parsed["summary"])
        self.assertEqual("Agent memory can use RAG.", parsed["body_sections"]["core_idea"])

    def test_parse_ignores_provenance_block(self) -> None:
        note = _note()
        markdown = render_obsidian_note(note, NoteRegistry.from_notes([note]))

        parsed = parse_note_markdown(markdown)

        # le fonti sono campi 'macchina': non devono finire tra alias/tag
        self.assertNotIn("raw/a.md", parsed["aliases"])
        self.assertNotIn("section 1", parsed["tags"])


if __name__ == "__main__":
    unittest.main()
