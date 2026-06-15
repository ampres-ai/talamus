import unittest

from benchmarks.shootout.runner import JudgedCorpus, run_shootout
from benchmarks.shootout.systems.fake import FakeSystem


class RunnerTests(unittest.TestCase):
    def _corpus(self) -> JudgedCorpus:
        return JudgedCorpus(
            docs=[
                ("d1", "Cats", "the cat sat on the mat"),
                ("d2", "Dogs", "the dog ran in the park"),
                ("d3", "Birds", "the bird flew over the cat"),
            ],
            queries={"q1": "cat", "q2": "dog park"},
            qrels={"q1": {"d1": 1, "d3": 1}, "q2": {"d2": 1}},
        )

    def test_runs_each_system_and_aggregates(self) -> None:
        result = run_shootout([FakeSystem()], self._corpus(), k=3)
        row = result["systems"]["fake"]
        self.assertEqual(row["n_queries"], 2)
        self.assertGreater(row["recall_at_k"], 0.0)
        self.assertIn("ingest", row)
        self.assertEqual(row["ingest"]["llm_calls"], 0)

    def test_per_query_detail_is_recorded(self) -> None:
        result = run_shootout([FakeSystem()], self._corpus(), k=3)
        cases = result["systems"]["fake"]["cases"]
        self.assertEqual({c["query_id"] for c in cases}, {"q1", "q2"})
