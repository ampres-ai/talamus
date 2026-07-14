"""Watch mode: new files in the watched folder become notes automatically;
unchanged files are hash-skipped, multi-chunk documents wait for explicit
consent, the daily cap bounds the spend, and the brain's own output is never
re-ingested."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.store import load_notes
from talamus.watch import scan_once
from tests.support import FakeLLMProvider


def _extraction(title: str) -> str:
    return json.dumps(
        [
            {
                "title": title,
                "retrieval_text": "appunti notes",
                "summary": "Una nota.",
                "supported_claims": ["x"],
                "confidence": 0.9,
            }
        ]
    )


class WatchTests(unittest.TestCase):
    def _paths(self, tmp: str) -> TalamusPaths:
        paths = TalamusPaths(Path(tmp))
        paths.ensure_directories()
        return paths

    def test_new_file_is_ingested_and_then_hash_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            (Path(tmp) / "appunti.md").write_text("una nota nuova", encoding="utf-8")
            llm = FakeLLMProvider([_extraction("Appunti")])

            first = scan_once(paths, Path(tmp), StaticRouter(llm))
            self.assertEqual(["appunti.md"], first["ingested"])
            self.assertEqual(1, len(load_notes(paths)))

            second = scan_once(paths, Path(tmp), StaticRouter(FakeLLMProvider([])))
            self.assertEqual([], second["ingested"])  # unchanged: no LLM spend

    def test_multichunk_documents_wait_for_explicit_consent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            big = "paragrafo lungo\n\n" * 3000  # > CHUNK_CHARS: needs ingest --yes
            (Path(tmp) / "libro.md").write_text(big, encoding="utf-8")
            llm = FakeLLMProvider([])

            result = scan_once(paths, Path(tmp), StaticRouter(llm))

            self.assertEqual(["libro.md"], result["skipped_large"])
            self.assertEqual([], result["ingested"])
            self.assertEqual(0, len(llm.prompts))

    def test_daily_cap_bounds_the_spend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            (Path(tmp) / "a.md").write_text("nota a", encoding="utf-8")
            (Path(tmp) / "b.md").write_text("nota b", encoding="utf-8")
            llm = FakeLLMProvider([_extraction("Nota A")])

            result = scan_once(paths, Path(tmp), StaticRouter(llm), daily_cap=1)

            self.assertEqual(1, len(result["ingested"]))
            self.assertEqual(1, result["capped"])

    def test_brain_output_is_never_reingested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            (paths.notes / "Esistente.md").write_text("# Esistente", encoding="utf-8")
            (paths.talamus_dir / "x.md").write_text("interno", encoding="utf-8")
            llm = FakeLLMProvider([])

            result = scan_once(paths, Path(tmp), StaticRouter(llm))

            self.assertEqual([], result["ingested"])
            self.assertEqual(0, len(llm.prompts))


if __name__ == "__main__":
    unittest.main()
