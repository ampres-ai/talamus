"""RS8 adaptive-trigram floor: locks the measured SciFact ranking win so a future
change to the blend cannot silently regress it. Heavy (downloads BEIR SciFact),
gated by TALAMUS_BENCH_HEAVY — not in the normal CI run."""

import os
import statistics
import unittest

from benchmarks.shootout import metrics as M
from benchmarks.shootout.corpora.judged import load_beir
from benchmarks.shootout.systems.talamus_system import TalamusSearch


@unittest.skipUnless(os.environ.get("TALAMUS_BENCH_HEAVY"), "network/download")
class AdaptiveTrigramScifactFloorTests(unittest.TestCase):
    def test_scifact_ranking_holds_the_rs8_adaptive_win(self):
        corpus = load_beir("scifact")
        system = TalamusSearch()
        system.ingest(corpus.as_docs())
        ndcg, rec = [], []
        for qid, q in corpus.queries.items():
            ids = system.query(q, 10)
            ndcg.append(M.ndcg_at_k(ids, corpus.qrels.get(qid, {}), 10))
            rec.append(M.recall_at_k(ids, set(corpus.qrels.get(qid, {})), 10))
        mean_ndcg, mean_rec = statistics.mean(ndcg), statistics.mean(rec)
        # measured at scale 0.3: nDCG 0.664, recall 0.797 (beats BM25's 0.652/0.776)
        self.assertGreaterEqual(
            mean_ndcg, 0.63, f"SciFact nDCG {mean_ndcg:.3f} fell below the RS8 adaptive floor"
        )
        self.assertGreaterEqual(
            mean_rec, 0.77, f"SciFact recall {mean_rec:.3f} fell below the RS8 adaptive floor"
        )


if __name__ == "__main__":
    unittest.main()
