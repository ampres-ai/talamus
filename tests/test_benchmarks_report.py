import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.shootout.report import provenance, write_report


class ReportTests(unittest.TestCase):
    def _result(self) -> dict:
        return {
            "k": 10,
            "n_docs": 3,
            "n_queries": 2,
            "systems": {
                "talamus-smart": {
                    "recall_at_k": 0.9,
                    "mrr": 0.8,
                    "hit_rate": 0.95,
                    "ndcg_at_k": 0.88,
                    "latency_ms_p50": 12.0,
                    "ingest": {"llm_calls": 5, "input_tokens": 100, "index_bytes": 42},
                    "cases": [],
                }
            },
        }

    def test_provenance_has_commit_and_timestamp(self) -> None:
        stamp = provenance(Path.cwd(), {"talamus": "x"})
        self.assertIn("git", stamp)
        self.assertIn("generated_at", stamp)
        self.assertEqual(stamp["versions"]["talamus"], "x")

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = write_report(self._result(), {"talamus": "x"}, out, "phase1")
            data = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertIn("provenance", data)
            self.assertIn("talamus-smart", data["systems"])
            md = paths["md"].read_text(encoding="utf-8")
            self.assertIn("talamus-smart", md)
            self.assertIn("recall", md.lower())
