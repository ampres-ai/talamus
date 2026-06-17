import unittest

from benchmarks.shootout.systems.base import Doc
from benchmarks.shootout.systems.llmwiki_system import LLMWikiSystem


class _FakeLLM:
    def complete(self, prompt):
        return "keywords: quantization memory bits"


class LLMWikiTests(unittest.TestCase):
    def test_ingests_and_retrieves(self):
        sys = LLMWikiSystem(_FakeLLM())
        sys.ingest([Doc("d1", "Quantization", "reduce bits to save memory")])
        self.assertEqual(sys.query("memory bits", 5), ["d1"])

    def test_no_match_returns_empty(self):
        sys = LLMWikiSystem(_FakeLLM())
        sys.ingest([Doc("d1", "Quantization", "reduce bits")])
        self.assertEqual(sys.query("unrelated zzz", 5), [])

    def test_llm_failure_degrades_to_plain_text(self):
        class _BadLLM:
            def complete(self, prompt):
                raise RuntimeError("engine down")

        sys = LLMWikiSystem(_BadLLM())
        stats = sys.ingest([Doc("d1", "Quantization", "reduce bits to save memory")])
        self.assertEqual(stats.llm_calls, 1)
        self.assertEqual(sys.query("memory", 5), ["d1"])  # still retrievable on title+text


if __name__ == "__main__":
    unittest.main()
