import unittest

from talamus.adapters.llm import ClaudeCliProvider, _default_runner
from talamus.errors import EngineNotFound


class LLMAdapterTests(unittest.TestCase):
    def test_default_runner_errors_on_missing_command(self) -> None:
        with self.assertRaises(EngineNotFound):
            _default_runner(["definitely-not-a-real-command-xyz"], "prompt")

    def test_claude_cli_builds_print_mode_command(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            captured["prompt"] = prompt
            return "risposta"

        provider = ClaudeCliProvider(runner=fake_runner)

        result = provider.complete("ciao")

        self.assertEqual("risposta", result)
        self.assertEqual(["claude", "-p"], captured["args"])
        self.assertEqual("ciao", captured["prompt"])


if __name__ == "__main__":
    unittest.main()
