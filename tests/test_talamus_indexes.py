import tempfile
import unittest
from pathlib import Path
from unittest import mock

from talamus.indexes import (
    backend_info,
    build_search_index,
    postings_path,
    search_index,
    sqlite_path,
)
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import load_notes, rebuild_indexes, write_note


def _note(title: str, retrieval: str, aliases: list[str] | None = None) -> CanonicalNote:
    src = SourceRef("raw/a.md", "norm/a#1", "s", "sha256:x", ["c"])
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=aliases or [],
        folder="",
        tags=[],
        summary=f"{title}.",
        retrieval_text=retrieval,
        body_sections={"d": retrieval},
        proposed_links=[],
        relations=[],
        sources=[src],
        confidence=0.9,
    )


def _brain(tmp: str) -> TalamusPaths:
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    write_note(paths, _note("Reranking", "riordina i candidati del recupero per pertinenza"))
    write_note(paths, _note("Vector Store", "memorizza embeddings per la ricerca", ["VS"]))
    write_note(paths, _note("Provenienza", "ogni scheda conserva la fonte originale"))
    rebuild_indexes(paths)
    return paths


class PersistentIndexTests(unittest.TestCase):
    def test_rebuild_creates_persistent_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            info = backend_info(paths)
            self.assertIn(info["backend"], ("sqlite-fts5", "json-postings"))
            self.assertGreater(info["bytes"], 0)

    def test_search_finds_stemmed_matches_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            hits = search_index(paths, "come riordino i candidati?", limit=5)
            self.assertTrue(hits)
            top = hits[0]
            self.assertEqual(top["title"], "Reranking")
            self.assertEqual(top["summary"], "Reranking.")  # metadata travels with the hit
            self.assertGreater(top["score"], 0)

    def test_postings_fallback_matches_sqlite_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            sqlite_hits = search_index(paths, "embeddings ricerca", limit=3)
            with mock.patch("talamus.indexes._fts5_available", return_value=False):
                build_search_index(paths, load_notes(paths))
            self.assertFalse(sqlite_path(paths).is_file())
            self.assertTrue(postings_path(paths).is_file())
            posting_hits = search_index(paths, "embeddings ricerca", limit=3)
            self.assertTrue(posting_hits)
            if sqlite_hits:
                self.assertEqual(posting_hits[0]["title"], sqlite_hits[0]["title"])

    def test_legacy_fallback_when_no_persistent_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            sqlite_path(paths).unlink(missing_ok=True)
            postings_path(paths).unlink(missing_ok=True)
            hits = search_index(paths, "fonte originale", limit=3)
            self.assertTrue(hits)
            self.assertEqual(hits[0]["title"], "Provenienza")

    def test_empty_query_returns_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            self.assertEqual(search_index(paths, "", limit=3), [])


if __name__ == "__main__":
    unittest.main()
