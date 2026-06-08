import tempfile
import unittest
from pathlib import Path

from talamus.search import BM25Index


class TalamusSearchTests(unittest.TestCase):
    def test_bm25_returns_best_matching_document(self) -> None:
        index = BM25Index()
        index.add("rag", "retrieval augmented generation external knowledge documents")
        index.add("finetuning", "training model weights supervised examples")

        results = index.search("external documents retrieval", limit=1)

        self.assertEqual("rag", results[0]["id"])
        self.assertGreater(results[0]["score"], 0)

    def test_empty_index_returns_no_results(self) -> None:
        self.assertEqual([], BM25Index().search("anything"))

    def test_bm25_round_trips_to_json(self) -> None:
        index = BM25Index()
        index.add("rag", "retrieval augmented generation external knowledge")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bm25.json"
            index.save(path)
            loaded = BM25Index.load(path)

        self.assertEqual("rag", loaded.search("external knowledge", limit=1)[0]["id"])


if __name__ == "__main__":
    unittest.main()
