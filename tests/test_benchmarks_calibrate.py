import unittest

from benchmarks.ask_eval.calibrate import calibrate


class _FakeLLM:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        return "GROUNDED"


class CalibrateTests(unittest.TestCase):
    def test_times_calls_and_recommends_local_when_fast(self):
        llm = _FakeLLM()
        out = calibrate(llm, n=3, threshold_s=8.0)
        self.assertEqual(out["calls"], 3)
        self.assertEqual(llm.calls, 3)
        self.assertGreaterEqual(out["seconds_per_call"], 0.0)
        self.assertEqual(out["recommend"], "local-primary")  # fake is instant

    def test_recommends_invert_when_threshold_zero(self):
        out = calibrate(_FakeLLM(), n=2, threshold_s=0.0)
        self.assertEqual(out["recommend"], "invert")


if __name__ == "__main__":
    unittest.main()
