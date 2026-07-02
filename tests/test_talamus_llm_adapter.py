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

    def test_default_runner_surfaces_stdout_when_stderr_empty(self) -> None:
        import subprocess
        from unittest.mock import patch

        from talamus.errors import EngineFailed

        # CLIs like `claude -p` write their error to stdout and exit non-zero with
        # empty stderr; the failure message must still carry the real reason.
        fake = subprocess.CompletedProcess(
            args=["claude", "-p"],
            returncode=1,
            stdout="Failed to authenticate. API Error: 401 Invalid authentication credentials",
            stderr="",
        )
        with (
            patch("talamus.adapters.llm.shutil.which", return_value="claude"),
            patch("talamus.adapters.llm.subprocess.run", return_value=fake),
        ):
            with self.assertRaises(EngineFailed) as ctx:
                _default_runner(["claude", "-p"], "hi")
        self.assertIn("401", str(ctx.exception))

    def test_claude_cli_applies_tier_model(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            return "ok"

        from talamus.adapters.llm import build_provider_for_task
        from talamus.config import TalamusConfig

        provider = build_provider_for_task("claude-cli", TalamusConfig.default(), "economy", "low")
        provider._runner = fake_runner  # type: ignore[attr-defined]
        provider.complete("hi")
        self.assertIn("--model", captured["args"])
        self.assertIn("haiku", captured["args"])

    def test_codex_cli_applies_tier_model_and_effort(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            return "ok"

        from talamus.adapters.llm import build_provider_for_task
        from talamus.config import TalamusConfig

        provider = build_provider_for_task("codex-cli", TalamusConfig.default(), "quality", "high")
        provider._runner = fake_runner  # type: ignore[attr-defined]
        provider.complete("hi")
        self.assertIn("gpt-5.5", captured["args"])
        self.assertIn("model_reasoning_effort=high", " ".join(captured["args"]))

    def test_gemini_cli_ignores_unsupported_effort(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            return "ok"

        from talamus.adapters.llm import build_provider_for_task
        from talamus.config import TalamusConfig

        provider = build_provider_for_task("gemini-cli", TalamusConfig.default(), "economy", "high")
        provider._runner = fake_runner  # type: ignore[attr-defined]
        provider.complete("hi")
        self.assertIn("gemini-2.5-flash", captured["args"])
        self.assertNotIn("high", captured["args"])  # effort silently ignored

    def test_ollama_falls_back_to_the_configured_model_when_untiered(self) -> None:
        from dataclasses import replace

        from talamus.adapters.llm import build_provider_for_task
        from talamus.config import TalamusConfig

        config = replace(TalamusConfig.default(), llm_model="gemma3n")
        provider = build_provider_for_task("ollama", config, "quality", "high")
        self.assertEqual(provider._model, "gemma3n")  # type: ignore[attr-defined]

    def test_provider_models_override_wins_over_the_builtin_tier_map(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            return "ok"

        from dataclasses import replace

        from talamus.adapters.llm import build_provider_for_task
        from talamus.config import TalamusConfig

        config = replace(
            TalamusConfig.default(), provider_models={"claude-cli": {"economy": "sonnet"}}
        )
        provider = build_provider_for_task("claude-cli", config, "economy", "low")
        provider._runner = fake_runner  # type: ignore[attr-defined]
        provider.complete("hi")
        self.assertIn("sonnet", captured["args"])

    def test_canonical_provider_normalizes_aliases(self) -> None:
        from talamus.adapters.llm import canonical_provider

        self.assertEqual(canonical_provider("codex"), "codex-cli")
        self.assertEqual(canonical_provider("gemini"), "gemini-cli")
        self.assertEqual(canonical_provider("api"), "anthropic-api")
        self.assertEqual(canonical_provider("claude-cli"), "claude-cli")

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
