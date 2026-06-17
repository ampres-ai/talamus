import tempfile
import unittest
from pathlib import Path

from benchmarks.ask_eval.judges import CachingJudge, agreement


class _CountingLLM:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        return self.reply


class CachingJudgeTests(unittest.TestCase):
    def test_calls_once_per_unique_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            inner = _CountingLLM("GROUNDED")
            judge = CachingJudge(inner, Path(tmp) / "verdicts.json")
            a = judge.complete("same prompt")
            b = judge.complete("same prompt")
            self.assertEqual(a, "GROUNDED")
            self.assertEqual(b, "GROUNDED")
            self.assertEqual(inner.calls, 1)  # second served from cache

    def test_cache_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verdicts.json"
            inner = _CountingLLM("CORRECT")
            CachingJudge(inner, path).complete("q")
            inner2 = _CountingLLM("CORRECT")
            again = CachingJudge(inner2, path).complete("q")
            self.assertEqual(again, "CORRECT")
            self.assertEqual(inner2.calls, 0)  # loaded from disk


class AgreementTests(unittest.TestCase):
    def test_agreement_fraction(self):
        primary = ["correct", "wrong", "partial", "correct"]
        cross = ["correct", "wrong", "wrong", "correct"]
        self.assertEqual(agreement(primary, cross), 0.75)

    def test_empty(self):
        self.assertEqual(agreement([], []), 0.0)


if __name__ == "__main__":
    unittest.main()
