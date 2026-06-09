import os
import unittest

from talamus.adapters.llm import (
    AnthropicApiProvider,
    ClaudeCliProvider,
    OllamaProvider,
    _default_runner,
    build_provider,
)
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

    def test_ollama_provider_builds_run_command(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            return "ok"

        OllamaProvider("mistral", runner=fake_runner).complete("hi")
        self.assertEqual(["ollama", "run", "mistral"], captured["args"])

    def test_build_provider_selects_type(self) -> None:
        self.assertIsInstance(build_provider("claude-cli"), ClaudeCliProvider)
        self.assertIsInstance(build_provider("ollama"), OllamaProvider)
        self.assertIsInstance(build_provider("anthropic-api"), AnthropicApiProvider)
        with self.assertRaises(EngineNotFound):
            build_provider("nope")

    def test_anthropic_provider_uses_poster(self) -> None:
        def fake_poster(url: str, headers: dict, payload: dict) -> dict:
            return {"content": [{"text": "ciao"}]}

        os.environ["ANTHROPIC_API_KEY"] = "k"
        try:
            self.assertEqual("ciao", AnthropicApiProvider(poster=fake_poster).complete("x"))
        finally:
            del os.environ["ANTHROPIC_API_KEY"]


if __name__ == "__main__":
    unittest.main()
