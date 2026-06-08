import unittest

from talamus.models import CanonicalNote, ProposedLink, Relation, SourceRef


class TalamusModelsTests(unittest.TestCase):
    def test_canonical_note_requires_source_for_supported_claims(self) -> None:
        note = CanonicalNote(
            note_id="rag",
            title="Retrieval-Augmented Generation",
            aliases=["RAG"],
            folder="Retrieval",
            tags=["retrieval"],
            summary="Human summary.",
            retrieval_text="rag retrieval augmented generation external knowledge",
            body_sections={"core_idea": "RAG retrieves context before generation."},
            proposed_links=[],
            relations=[],
            sources=[],
            confidence=0.9,
        )

        self.assertEqual(["note has no sources"], note.validation_errors())

    def test_canonical_note_validates_confidence_range(self) -> None:
        note = CanonicalNote.minimal("RAG", confidence=1.5)

        self.assertIn("confidence must be between 0 and 1", note.validation_errors())

    def test_canonical_note_serializes_to_dict(self) -> None:
        source = SourceRef(
            raw_path="knowledge/raw/pdf/book.pdf",
            normalized_path="knowledge/normalized/pdf/book/sections/001.md",
            locator="pages 1-2",
            source_hash="sha256:abc",
            supported_claims=["RAG retrieves context."],
        )
        note = CanonicalNote.minimal("RAG", sources=[source])

        data = note.to_dict()

        self.assertEqual("RAG", data["title"])
        self.assertEqual("knowledge/raw/pdf/book.pdf", data["sources"][0]["raw_path"])


if __name__ == "__main__":
    unittest.main()
