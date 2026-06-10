import tempfile
import unittest
from pathlib import Path

from talamus.corpus import build_docs_corpus, build_synthetic_corpus
from talamus.paths import TalamusPaths
from talamus.recall import search_notes
from talamus.store import load_notes

_REPO_ROOT = Path(__file__).resolve().parent.parent


class DocsCorpusTests(unittest.TestCase):
    def test_builds_real_notes_from_repo_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            titles = build_docs_corpus(paths, _REPO_ROOT)
            self.assertGreater(len(titles), 20)
            self.assertEqual(len(titles), len(set(titles)))  # unique
            self.assertTrue(paths.graph_file.is_file())
            self.assertTrue(paths.index_file.is_file())
            # provenance points at real repo files
            note = load_notes(paths)[0]
            self.assertTrue(note.sources)
            self.assertTrue(note.sources[0].raw_path.endswith(".md"))
            # the corpus is searchable with real questions
            results = search_notes(paths, "recupero retrieval ricerca note")
            self.assertTrue(results)

    def test_corpus_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            titles_a = build_docs_corpus(TalamusPaths(Path(a)), _REPO_ROOT)
            titles_b = build_docs_corpus(TalamusPaths(Path(b)), _REPO_ROOT)
            self.assertEqual(titles_a, titles_b)


class SyntheticCorpusTests(unittest.TestCase):
    def test_builds_n_searchable_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            count = build_synthetic_corpus(paths, 25, seed=7)
            self.assertEqual(count, 25)
            self.assertEqual(len(list(paths.notes.glob("*.md"))), 25)
            results = search_notes(paths, "concetto00003")
            self.assertTrue(any(r["title"] == "Nota sintetica 00003" for r in results))

    def test_same_seed_same_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            build_synthetic_corpus(TalamusPaths(Path(a)), 10, seed=3)
            build_synthetic_corpus(TalamusPaths(Path(b)), 10, seed=3)
            text_a = sorted(p.read_text(encoding="utf-8") for p in Path(a, "notes").glob("*.md"))
            text_b = sorted(p.read_text(encoding="utf-8") for p in Path(b, "notes").glob("*.md"))
            self.assertEqual(text_a, text_b)


if __name__ == "__main__":
    unittest.main()
