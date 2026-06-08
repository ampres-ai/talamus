import tempfile
import unittest
from pathlib import Path

from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.recall import read_note_text, recall_context, search_notes
from talamus.store import rebuild_indexes, write_note


def _note(title: str, summary: str, retrieval: str) -> CanonicalNote:
    src = SourceRef("raw/a.md", "norm/a#1", "section 1", "sha256:x", ["claim"])
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=[],
        folder="",
        tags=[],
        summary=summary,
        retrieval_text=retrieval,
        body_sections={"definizione": summary},
        proposed_links=[],
        relations=[],
        sources=[src],
        confidence=0.9,
    )


class RecallTests(unittest.TestCase):
    def _brain(self, tmp: str) -> TalamusPaths:
        paths = TalamusPaths(Path(tmp))
        paths.ensure_directories()
        write_note(paths, _note("Retrieval-Augmented Generation", "Collega il modello a fonti esterne.", "rag fonti esterne documenti recupero"))
        write_note(paths, _note("Vector Store", "Memorizza embeddings per la ricerca.", "vector store embeddings"))
        rebuild_indexes(paths)
        return paths

    def test_search_returns_relevant_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._brain(tmp)
            results = search_notes(paths, "come recupero documenti da fonti esterne?")
            self.assertTrue(results)
            self.assertEqual("Retrieval-Augmented Generation", results[0]["title"])
            self.assertIn("fonti esterne", results[0]["summary"])

    def test_read_note_returns_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._brain(tmp)
            text = read_note_text(paths, "Vector Store")
            self.assertIsNotNone(text)
            self.assertIn("# Vector Store", text)

    def test_read_note_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._brain(tmp)
            self.assertIsNone(read_note_text(paths, "Nonexistent"))

    def test_recall_context_includes_note_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._brain(tmp)
            ctx = recall_context(paths, "come collego il modello a fonti esterne?")
            self.assertIn("Retrieval-Augmented Generation", ctx)

    def test_recall_empty_brain_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            rebuild_indexes(paths)
            ctx = recall_context(paths, "qualunque cosa")
            self.assertIn("Nessun contesto", ctx)


if __name__ == "__main__":
    unittest.main()
