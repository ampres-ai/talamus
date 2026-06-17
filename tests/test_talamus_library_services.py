import tempfile
import unittest
from pathlib import Path

from talamus.demo import create_demo_brain
from talamus.paths import TalamusPaths
from talamus.services.library import get_library_note, list_library_notes


class TalamusLibraryServiceTests(unittest.TestCase):
    def test_list_library_notes_returns_sorted_summaries_with_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))

            result = list_library_notes(root)

        self.assertTrue(result.success, result.message)
        report = result.data
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(3, report.note_count)
        titles = [note.title for note in report.notes]
        self.assertEqual(sorted(titles, key=str.lower), titles)
        embedding = next(note for note in report.notes if note.title == "Embedding")
        self.assertEqual(1, embedding.source_count)
        self.assertEqual(1, embedding.relation_count)
        self.assertEqual(0, embedding.proposed_link_count)
        self.assertTrue(embedding.markdown_path.endswith("Embedding.md"))

    def test_get_library_note_returns_metadata_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))

            result = get_library_note(root, "Embedding")

        self.assertTrue(result.success, result.message)
        detail = result.data
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertTrue(detail.found)
        self.assertEqual("Embedding", detail.title)
        self.assertIn("# Embedding", detail.markdown)
        self.assertIn("definizione", detail.body_sections)
        self.assertEqual(1, len(detail.sources))
        self.assertEqual("part-of", detail.relations[0]["relation"])

    def test_get_missing_library_note_returns_failed_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))

            result = get_library_note(root, "Missing")

        self.assertFalse(result.success)
        self.assertEqual("library_note_not_found", result.code)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertFalse(result.data.found)


if __name__ == "__main__":
    unittest.main()
