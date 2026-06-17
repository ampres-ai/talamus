import time
import unittest

from benchmarks.ask_eval.timeout_llm import TimeoutLLM


class _Hang:
    def complete(self, prompt: str) -> str:
        time.sleep(30)
        return "never"


class _Fast:
    def complete(self, prompt: str) -> str:
        return "ok"


class _Boom:
    def complete(self, prompt: str) -> str:
        raise ValueError("inner failure")


class TimeoutLLMTests(unittest.TestCase):
    def test_fast_call_returns(self) -> None:
        self.assertEqual(TimeoutLLM(_Fast(), seconds=2).complete("x"), "ok")

    def test_hung_call_times_out_quickly(self) -> None:
        start = time.time()
        with self.assertRaises(TimeoutError):
            TimeoutLLM(_Hang(), seconds=0.3).complete("x")
        self.assertLess(time.time() - start, 5)  # abandons fast, does not wait 30s

    def test_inner_error_propagates(self) -> None:
        with self.assertRaises(ValueError):
            TimeoutLLM(_Boom(), seconds=2).complete("x")


if __name__ == "__main__":
    unittest.main()
