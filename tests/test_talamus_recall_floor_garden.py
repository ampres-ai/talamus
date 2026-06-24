"""Garden corpus recall floor (P1.5) — the domain-diverse anti-overfit gate.

The garden corpus spans six unrelated domains (cooking, astronomy, law, history,
biology, personal finance). This FAST-tier test re-runs the judged eval on the
deterministic build and fails if a change regresses retrieval below a safety floor.
It complements the docs recall floor: a change must keep working across domains, not
just on the repo's own documentation.
"""

import tempfile
import unittest
from pathlib import Path

from talamus.corpus import build_garden_corpus
from talamus.eval import evaluate, load_cases, search_retriever
from talamus.paths import TalamusPaths

_REPO_ROOT = Path(__file__).resolve().parent.parent
# measured 0.952 / 0.909 / 1.000 on 2026-06-24; floor = measured - safety margin
_FLOOR_RECALL = 0.90
_FLOOR_MRR = 0.85
_FLOOR_HIT = 0.90


class GardenRecallFloorTests(unittest.TestCase):
    def test_garden_retrieval_stays_above_the_floor(self) -> None:
        cases_file = _REPO_ROOT / "examples" / "eval-cases-garden.json"
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            build_garden_corpus(paths, _REPO_ROOT)
            report = evaluate(load_cases(cases_file), search_retriever(paths), k=5)
        self.assertGreaterEqual(
            report.recall_at_k,
            _FLOOR_RECALL,
            f"garden recall@5 {report.recall_at_k:.3f} fell below the floor "
            f"{_FLOOR_RECALL} — a change regressed cross-domain retrieval",
        )
        self.assertGreaterEqual(report.mrr, _FLOOR_MRR)
        self.assertGreaterEqual(report.hit_rate, _FLOOR_HIT)


if __name__ == "__main__":
    unittest.main()
