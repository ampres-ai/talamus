import importlib.util
import unittest

from benchmarks.shootout.runner import JudgedCorpus, run_shootout


@unittest.skipUnless(importlib.util.find_spec("rank_bm25"), "rank-bm25 not installed")
class BM25SystemTests(unittest.TestCase):
    def test_bm25_ranks_relevant_doc_first(self) -> None:
        from benchmarks.shootout.systems.bm25_system import BM25System

        # BM25's Okapi IDF needs a non-degenerate corpus: on 2 docs a term in 1
        # doc gets IDF 0. Five docs keep the discriminating terms informative.
        corpus = JudgedCorpus(
            docs=[
                ("d1", "Quantization", "reduce the bits of model weights to save memory"),
                ("d2", "Reranking", "reorder candidate documents by relevance"),
                ("d3", "Attention", "the transformer attention mechanism over tokens"),
                ("d4", "Embedding", "dense vector representation of meaning"),
                ("d5", "Sampling", "temperature controls randomness of generation"),
            ],
            queries={"q1": "quantization memory bits"},
            qrels={"q1": {"d1": 1}},
        )
        result = run_shootout([BM25System()], corpus, k=2)
        self.assertEqual(result["systems"]["bm25"]["hit_rate"], 1.0)
        self.assertEqual(result["systems"]["bm25"]["ingest"]["llm_calls"], 0)
