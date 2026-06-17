import unittest

from benchmarks.agent_mem.task import AgentMemCase, score_recall


class _FakeMem:
    def __init__(self):
        self.store = []

    def remember(self, text, key):
        self.store.append((key, text))

    def recall(self, query, k):
        qa = set(query.lower().split())
        ranked = [key for key, text in self.store if qa & set(text.lower().split())]
        return ranked[:k]


class AgentMemTests(unittest.TestCase):
    def test_hit_when_right_key_returned(self):
        cases = [AgentMemCase(query="deploy on friday policy", want_key="k1")]
        mem = _FakeMem()
        mem.remember("never deploy on friday", "k1")
        mem.remember("use tabs not spaces", "k2")
        out = score_recall(mem, cases, k=3)
        self.assertEqual(out["hit_rate"], 1.0)
        self.assertEqual(out["n"], 1)

    def test_miss_when_wrong_key(self):
        cases = [AgentMemCase(query="completely unrelated topic", want_key="k1")]
        mem = _FakeMem()
        mem.remember("never deploy on friday", "k1")
        out = score_recall(mem, cases, k=3)
        self.assertEqual(out["hit_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
