import json
import tempfile
import unittest
from pathlib import Path

from talamus.ingest import ingest_dir
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from tests.support import FakeLLMProvider


def _llm(count: int) -> FakeLLMProvider:
    note = json.dumps(
        [
            {
                "title": "N",
                "retrieval_text": "x",
                "summary": "s",
                "supported_claims": ["x"],
                "confidence": 0.9,
            }
        ]
    )
    return FakeLLMProvider([note for _ in range(count)])


class BulkTests(unittest.TestCase):
    def test_ingest_dir_then_incremental_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as src:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            (Path(src) / "a.md").write_text("# A\nalpha", encoding="utf-8")
            (Path(src) / "b.md").write_text("# B\nbeta", encoding="utf-8")

            first = ingest_dir(paths, Path(src), StaticRouter(_llm(2)))
            self.assertEqual(2, first["files"])

            second = ingest_dir(paths, Path(src), StaticRouter(_llm(2)))
            self.assertEqual(0, second["files"])
            self.assertEqual(2, second["skipped"])


if __name__ == "__main__":
    unittest.main()
