import json
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


class CiNegativesTests(unittest.TestCase):
    def test_ci_negatives_are_well_formed(self):
        path = _REPO_ROOT / "benchmarks" / "ask_eval" / "negatives_ci.json"
        cases = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 5)
        for case in cases:
            self.assertTrue(case["question"])
            self.assertFalse(case.get("relevant"))  # negatives have no relevant docs


if __name__ == "__main__":
    unittest.main()
