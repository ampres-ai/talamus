import os
import unittest

from benchmarks.shootout.corpora.judged import load_beir


@unittest.skipUnless(os.environ.get("TALAMUS_BENCH_HEAVY"), "network/download")
class BeirDatasetsTests(unittest.TestCase):
    def test_load_nfcorpus_has_queries_and_qrels(self):
        corpus = load_beir("nfcorpus")
        self.assertGreater(corpus.n_docs, 100)
        self.assertGreater(len(corpus.queries), 0)
        self.assertTrue(all(corpus.qrels.get(q) for q in corpus.queries))


if __name__ == "__main__":
    unittest.main()
