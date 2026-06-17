import os
import unittest

from benchmarks.shootout.corpora.miracl import miracl_rows_to_corpus


class MiraclAdapterTests(unittest.TestCase):
    def test_builds_pool_and_qrels(self):
        rows = [
            {
                "query_id": "1",
                "query": "che cos'è la quantizzazione",
                "positive_passages": [
                    {"docid": "p1", "title": "Quantizzazione", "text": "ridurre i bit"}
                ],
                "negative_passages": [
                    {"docid": "n1", "title": "Altro", "text": "testo non rilevante"}
                ],
            }
        ]
        corpus = miracl_rows_to_corpus(rows)
        self.assertEqual(corpus.queries, {"1": "che cos'è la quantizzazione"})
        self.assertEqual(corpus.qrels, {"1": {"p1": 1}})
        ids = {doc_id for doc_id, _t, _x in corpus.docs}
        self.assertEqual(ids, {"p1", "n1"})  # positives + hard negatives = the pool

    def test_drops_query_with_no_positives(self):
        rows = [{"query_id": "2", "query": "q", "positive_passages": [], "negative_passages": []}]
        corpus = miracl_rows_to_corpus(rows)
        self.assertEqual(corpus.queries, {})
        self.assertEqual(corpus.qrels, {})


@unittest.skipUnless(os.environ.get("TALAMUS_BENCH_HEAVY"), "network/download")
class MiraclNetworkTests(unittest.TestCase):
    def test_load_italian_dev(self):
        from benchmarks.shootout.corpora.miracl import load_miracl

        corpus = load_miracl("it", "dev", limit=20)
        self.assertGreater(corpus.n_docs, 0)
        self.assertGreater(len(corpus.queries), 0)


if __name__ == "__main__":
    unittest.main()
