import unittest

from benchmarks.shootout.metrics import hit_rate, mrr, ndcg_at_k, recall_at_k


class MetricsTests(unittest.TestCase):
    def test_recall_at_k(self) -> None:
        # 1 of 2 relevant docs found in the top 3
        self.assertAlmostEqual(recall_at_k(["a", "x", "y"], {"a", "b"}, 3), 0.5)
        self.assertEqual(recall_at_k(["x"], set(), 3), 0.0)  # no relevant -> 0 by convention

    def test_mrr_uses_first_relevant_rank(self) -> None:
        self.assertAlmostEqual(mrr(["x", "a", "b"], {"a"}), 1 / 2)
        self.assertEqual(mrr(["x", "y"], {"a"}), 0.0)

    def test_hit_rate_is_binary(self) -> None:
        self.assertEqual(hit_rate(["x", "a"], {"a"}, 2), 1.0)
        self.assertEqual(hit_rate(["x", "a"], {"a"}, 1), 0.0)  # not in top 1

    def test_ndcg_rewards_higher_grades_earlier(self) -> None:
        grades = {"a": 2, "b": 1}
        good = ndcg_at_k(["a", "b"], grades, 2)
        worse = ndcg_at_k(["b", "a"], grades, 2)
        self.assertAlmostEqual(good, 1.0)
        self.assertLess(worse, good)
