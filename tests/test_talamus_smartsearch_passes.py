import tempfile
import unittest
from pathlib import Path

from talamus.errors import EngineFailed
from talamus.paths import TalamusPaths
from talamus.smartsearch import expand_query_multi


class _SeqLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, prompt):
        out = self.replies[self.calls % len(self.replies)]
        self.calls += 1
        return out


class _DownLLM:
    def complete(self, prompt):
        raise EngineFailed("engine down")


class ExpandMultiTests(unittest.TestCase):
    def test_multi_pass_unions_unique_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            llm = _SeqLLM(["memory bits", "bits cost"])
            out = expand_query_multi(paths, "quantization", llm, passes=2)
            self.assertEqual(llm.calls, 2)
            for term in ("memory", "bits", "cost", "quantization"):
                self.assertIn(term, out)
            self.assertEqual(out.lower().split().count("bits"), 1)  # unioned, not duplicated

    def test_single_pass_delegates_to_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            llm = _SeqLLM(["memory bits"])
            out = expand_query_multi(paths, "quantization", llm, passes=1)
            self.assertIn("quantization", out)
            self.assertIn("memory", out)

    def test_engine_failure_degrades_to_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            out = expand_query_multi(paths, "quantization", _DownLLM(), passes=2)
            self.assertEqual(out, "quantization")  # never worse than the question


if __name__ == "__main__":
    unittest.main()
