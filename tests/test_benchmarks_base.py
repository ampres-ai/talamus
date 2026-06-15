import unittest

from benchmarks.shootout.systems.base import Doc, IngestStats
from benchmarks.shootout.systems.fake import FakeSystem


class BaseTypesTests(unittest.TestCase):
    def test_fake_system_ingests_and_queries_by_keyword(self) -> None:
        docs = [
            Doc("d1", "Cats", "the cat sat on the mat"),
            Doc("d2", "Dogs", "the dog ran in the park"),
            Doc("d3", "Birds", "the bird flew over the cat"),
        ]
        system = FakeSystem()
        stats = system.ingest(docs)
        self.assertIsInstance(stats, IngestStats)
        self.assertEqual(stats.llm_calls, 0)
        # ranks docs by how many query words they contain; ties broken by doc_id
        self.assertEqual(system.query("cat", k=2), ["d1", "d3"])
        self.assertEqual(system.query("dog park", k=1), ["d2"])

    def test_query_on_empty_index_returns_empty(self) -> None:
        self.assertEqual(FakeSystem().query("anything", k=5), [])
