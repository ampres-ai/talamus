import unittest

from benchmarks.shootout.runner import JudgedCorpus, run_shootout
from benchmarks.shootout.systems.talamus_system import TalamusSearch, TalamusSmart

from tests.support import FakeLLMProvider


class TalamusSystemTests(unittest.TestCase):
    def _corpus(self) -> JudgedCorpus:
        return JudgedCorpus(
            docs=[
                ("d1", "Quantization", "reduce the bits of model weights to save memory"),
                ("d2", "Reranking", "reorder candidate documents by relevance"),
            ],
            queries={"q1": "quantization memory"},
            qrels={"q1": {"d1": 1}},
        )

    def test_talamus_search_finds_the_relevant_doc(self) -> None:
        result = run_shootout([TalamusSearch()], self._corpus(), k=2)
        self.assertEqual(result["systems"]["talamus-search"]["hit_rate"], 1.0)

    def test_talamus_smart_expands_query_with_llm(self) -> None:
        smart = TalamusSmart(llm=FakeLLMProvider(["quantization bits memory"]))
        result = run_shootout([smart], self._corpus(), k=2)
        self.assertEqual(result["systems"]["talamus-smart"]["hit_rate"], 1.0)
        self.assertEqual(result["systems"]["talamus-smart"]["ingest"]["llm_calls"], 0)
