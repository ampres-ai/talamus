import tempfile
import unittest
from pathlib import Path

from talamus.demo import create_demo_brain
from talamus.paths import TalamusPaths
from talamus.services.query import (
    brain_overview,
    note_history_view,
    read_note,
    recall_brain,
    search_brain,
)


class QueryServiceTests(unittest.TestCase):
    def test_search_read_and_recall_demo_brain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))

            search = search_brain(root, "embedding", policy="project-only", limit=3)
            read = read_note(root, "Embedding")
            recall = recall_brain(root, "come funzionano gli embedding?", policy="project-only")

        self.assertTrue(search.success)
        self.assertIsNotNone(search.data)
        self.assertEqual("project-only", search.data.scope)
        self.assertTrue(any(hit.title == "Embedding" for hit in search.data.hits))
        self.assertTrue(read.success)
        self.assertIsNotNone(read.data)
        self.assertTrue(read.data.found)
        self.assertIn("# Embedding", read.data.markdown or "")
        self.assertTrue(recall.success)
        self.assertIsNotNone(recall.data)
        self.assertEqual("project-only", recall.data.scope)
        self.assertIn("Embedding", recall.data.context)

    def test_read_missing_note_returns_failed_result_with_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))

            result = read_note(root, "Missing")

        self.assertFalse(result.success)
        self.assertEqual("note_not_found", result.code)
        self.assertIsNotNone(result.data)
        self.assertFalse(result.data.found)
        self.assertIsNone(result.data.markdown)

    def test_recall_empty_brain_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = recall_brain(Path(tmp), "qualunque cosa", policy="project-only")

        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertIn("No relevant context", result.data.context)

    def test_brain_overview_returns_saved_domains(self) -> None:
        from talamus.domains import save_overview

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            save_overview(
                TalamusPaths(root),
                [{"name": "Models", "description": "ml", "members": ["Embedding"]}],
            )

            result = brain_overview(root)

        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertEqual("Models", result.data.domains[0]["name"])

    def test_note_history_view_reads_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))

            result = note_history_view(root, "Reranking")

        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertTrue(result.data.versions)


if __name__ == "__main__":
    unittest.main()
