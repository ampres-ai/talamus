import unittest

from benchmarks.shootout.corpora.judged import beir_to_corpus


class JudgedLoaderTests(unittest.TestCase):
    def test_adapts_beir_shape_to_judged_corpus(self) -> None:
        corpus = {
            "d1": {"title": "Cats", "text": "the cat sat"},
            "d2": {"title": "Dogs", "text": "the dog ran"},
        }
        queries = {"q1": "cat"}
        qrels = {"q1": {"d1": 1}}
        judged = beir_to_corpus(corpus, queries, qrels)
        self.assertEqual(judged.n_docs, 2)
        self.assertEqual(judged.queries, {"q1": "cat"})
        self.assertEqual(judged.qrels, {"q1": {"d1": 1}})
        ids = {doc_id for doc_id, _, _ in judged.docs}
        self.assertEqual(ids, {"d1", "d2"})

    def test_drops_queries_without_qrels(self) -> None:
        judged = beir_to_corpus(
            {"d1": {"title": "", "text": "x"}}, {"q1": "x", "q2": "y"}, {"q1": {"d1": 1}}
        )
        self.assertEqual(set(judged.queries), {"q1"})  # q2 has no judgments -> excluded
