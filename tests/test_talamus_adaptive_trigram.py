import dataclasses
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from talamus.indexes import (
    _trigram_scale,
    build_search_index,
    postings_path,
    search_index,
    sqlite_path,
)
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.textutil import is_monolingual_ascii, non_ascii_ratio


def _note(note_id, title, summary):
    src = SourceRef("raw/x.md", "raw/x.md#1", "bench", "sha256:x", [summary])
    n = CanonicalNote.minimal(title, sources=[src])
    return dataclasses.replace(
        n, note_id=note_id, summary=summary, retrieval_text=f"{title} {summary}"
    )


def _stored_monolingual(paths):
    if sqlite_path(paths).is_file():
        conn = sqlite3.connect(sqlite_path(paths))
        try:
            row = conn.execute("SELECT value FROM config WHERE key='monolingual'").fetchone()
            return bool(row and row[0] == "1")
        finally:
            conn.close()
    data = json.loads(postings_path(paths).read_text(encoding="utf-8"))
    return bool(data.get("monolingual"))


class DetectorTests(unittest.TestCase):
    def test_english_zero_non_ascii(self):
        self.assertEqual(non_ascii_ratio(["reduce model weights to save memory"]), 0.0)

    def test_italian_has_non_ascii(self):
        texts = ["ottimizzazione dell'inferenza perché serve velocità", "città però così"]
        self.assertGreater(non_ascii_ratio(texts), 0.0)
        self.assertFalse(is_monolingual_ascii(texts))

    def test_english_is_monolingual(self):
        self.assertTrue(is_monolingual_ascii(["quantization saves memory", "reranking reorders"]))

    def test_empty(self):
        self.assertEqual(non_ascii_ratio([]), 0.0)


class TrigramScaleTests(unittest.TestCase):
    def test_scales_only_when_monolingual(self):
        self.assertEqual(_trigram_scale(True, 0.3), 0.3)
        self.assertEqual(_trigram_scale(False, 0.3), 1.0)

    def test_default_ships_active(self):
        # The lever ships ON (default < 1.0); only monolingual corpora are damped
        from talamus.indexes import MONO_TRIGRAM_SCALE

        self.assertLess(MONO_TRIGRAM_SCALE, 1.0)
        self.assertEqual(_trigram_scale(True), MONO_TRIGRAM_SCALE)
        self.assertEqual(_trigram_scale(False), 1.0)


class BuildFlagTests(unittest.TestCase):
    def test_english_corpus_flagged_monolingual(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            notes = [
                _note("a", "Quantization", "reduce bits to save memory"),
                _note("b", "Reranking", "reorder candidates by relevance"),
            ]
            build_search_index(paths, notes)
            self.assertTrue(_stored_monolingual(paths))
            hits = search_index(paths, "memory bits", limit=2)
            self.assertTrue(hits and hits[0]["note_id"] in {"a", "b"})

    def test_italian_corpus_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            notes = [
                _note("a", "Quantizzazione", "ridurre i bit per così risparmiare memoria"),
                _note("b", "Riordino", "riordina i candidati perché contano davvero"),
            ]
            build_search_index(paths, notes)
            self.assertFalse(_stored_monolingual(paths))


if __name__ == "__main__":
    unittest.main()
