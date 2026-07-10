"""The recall floor — research gains, protected forever.

The 2026-06 recall research lifted production retrieval on the real 120-case
eval-set (recall@5 0.394 -> 0.492, MRR 0.333 -> 0.449). This test re-runs that
exact measurement and fails if anyone regresses it below a safety floor. It IS
the quality gate: changes to stemming, indexing or
ranking must keep beating these numbers or be rejected.
"""

import tempfile
import unittest
from pathlib import Path

from talamus.corpus import build_docs_corpus
from talamus.eval import evaluate, load_cases, search_retriever
from talamus.paths import TalamusPaths

_REPO_ROOT = Path(__file__).resolve().parent.parent
# measured 0.492 / 0.449 / 0.600 on 2026-06-11; floor = measured - safety margin
_FLOOR_RECALL = 0.45
_FLOOR_MRR = 0.40
_FLOOR_HIT = 0.55


class RecallFloorTests(unittest.TestCase):
    def test_production_retrieval_stays_above_the_research_floor(self) -> None:
        cases_file = _REPO_ROOT / "examples" / "eval-cases-real.json"
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            build_docs_corpus(paths, _REPO_ROOT)
            report = evaluate(load_cases(cases_file), search_retriever(paths), k=5)
        self.assertGreaterEqual(
            report.recall_at_k,
            _FLOOR_RECALL,
            f"recall@5 {report.recall_at_k:.3f} fell below the research floor "
            f"{_FLOOR_RECALL} — a change regressed retrieval quality",
        )
        self.assertGreaterEqual(report.mrr, _FLOOR_MRR)
        self.assertGreaterEqual(report.hit_rate, _FLOOR_HIT)


if __name__ == "__main__":
    unittest.main()
