import tempfile
import unittest
from pathlib import Path

from talamus.bench import (
    LLM_CALL_LEDGER,
    format_report,
    measure_latency,
    percentiles,
    routing_prompt_tokens,
)
from talamus.corpus import build_synthetic_corpus
from talamus.paths import TalamusPaths


class PercentilesTests(unittest.TestCase):
    def test_p50_p95(self) -> None:
        stats = percentiles([float(i) for i in range(1, 101)])
        self.assertEqual(stats["p50_ms"], 50.5)
        self.assertEqual(stats["p95_ms"], 95.0)
        self.assertEqual(stats["n_samples"], 100)

    def test_empty(self) -> None:
        self.assertEqual(percentiles([])["n_samples"], 0)


class RoutingTokensTests(unittest.TestCase):
    def test_curve_grows_with_notes(self) -> None:
        small = routing_prompt_tokens(100)
        big = routing_prompt_tokens(10000)
        self.assertGreater(big["prompt_tokens"], small["prompt_tokens"])
        self.assertEqual(small["n_domains"], 10)


class MeasureLatencyTests(unittest.TestCase):
    def test_returns_search_and_legacy_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            build_synthetic_corpus(paths, 20, render=False)
            stats = measure_latency(paths, 20)
            self.assertEqual(stats["n_notes"], 20)
            self.assertGreater(stats["search"]["n_samples"], 0)
            self.assertGreater(stats["legacy_scan"]["n_samples"], 0)


class ReportTests(unittest.TestCase):
    def test_format_report_renders_all_sections(self) -> None:
        result = {
            "generated_at": "2026-06-10T00:00:00",
            "git": "abc1234",
            "docs_corpus_notes": 74,
            "eval": {
                "k": 5,
                "n_cases": 2,
                "n_negative": 1,
                "recall_at_k": 0.5,
                "precision_at_k": 0.2,
                "mrr": 0.5,
                "hit_rate": 0.5,
                "negative_rejection": 0.0,
                "categories": {"direct": {"n": 1, "recall_at_k": 0.5, "mrr": 0.5, "hit_rate": 0.5}},
            },
            "latency": [
                {
                    "n_notes": 100,
                    "search": {"p50_ms": 1.0, "p95_ms": 2.0, "n_samples": 6},
                    "legacy_scan": {"p50_ms": 0.1, "p95_ms": 0.2, "n_samples": 18},
                }
            ],
            "routing_tokens": [{"n_notes": 100, "n_domains": 10, "prompt_tokens": 200}],
            "llm_call_ledger": LLM_CALL_LEDGER,
        }
        report = format_report(result)
        for marker in ("Baseline M0", "eval-set reale", "Latenza", "routing", "Ledger", "oneste"):
            self.assertIn(marker, report)


if __name__ == "__main__":
    unittest.main()
