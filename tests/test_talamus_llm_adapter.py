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

    def _failed_run(self, stdout: str = "", stderr: str = ""):
        import subprocess

        return subprocess.CompletedProcess(
            args=["engine"], returncode=1, stdout=stdout, stderr=stderr
        )

    def test_default_runner_maps_claude_usage_limit_to_limit_reached(self) -> None:
        from unittest.mock import patch

        from talamus.errors import EngineLimitReached

        fake = self._failed_run(stdout="You've hit your usage limit. Your limit resets at 3pm.")
        with (
            patch("talamus.adapters.llm.shutil.which", return_value="claude"),
            patch("talamus.adapters.llm.subprocess.run", return_value=fake),
        ):
            with self.assertRaises(EngineLimitReached) as ctx:
                _default_runner(["claude", "-p"], "hi")
        self.assertIn("resets at 3pm", str(ctx.exception))

    def test_default_runner_maps_out_of_credits_to_limit_reached(self) -> None:
        # the current claude-cli phrasing (2026): "out of usage credits · resets ..."
        from unittest.mock import patch

        from talamus.errors import EngineLimitReached

        fake = self._failed_run(
            stdout="You're out of usage credits · resets Jul 14, 1am (Europe/Rome)"
        )
        with (
            patch("talamus.adapters.llm.shutil.which", return_value="claude"),
            patch("talamus.adapters.llm.subprocess.run", return_value=fake),
        ):
            with self.assertRaises(EngineLimitReached) as ctx:
                _default_runner(["claude", "-p"], "hi")
        self.assertIn("resets Jul 14", str(ctx.exception))

    def test_default_runner_maps_429_and_quota_to_limit_reached(self) -> None:
        from unittest.mock import patch

        from talamus.errors import EngineLimitReached

        for detail in (
            "429 Too Many Requests",
            "RESOURCE_EXHAUSTED: Quota exceeded for quota metric",
            "Rate limit reached for gpt-5.5",
        ):
            fake = self._failed_run(stderr=detail)
            with (
                patch("talamus.adapters.llm.shutil.which", return_value="engine"),
                patch("talamus.adapters.llm.subprocess.run", return_value=fake),
            ):
                with self.assertRaises(EngineLimitReached):
                    _default_runner(["engine"], "hi")

    def test_limit_reached_is_still_an_engine_failure(self) -> None:
        # resumable jobs, ask degradation and smartsearch fallback all catch
        # EngineFailed — the limit error must flow through those same paths
        from talamus.errors import EngineFailed, EngineLimitReached

        self.assertTrue(issubclass(EngineLimitReached, EngineFailed))

    def test_plain_failure_is_not_misread_as_a_limit(self) -> None:
        from unittest.mock import patch

        from talamus.errors import EngineFailed, EngineLimitReached

        fake = self._failed_run(stdout="API Error: 401 Invalid authentication credentials")
        with (
            patch("talamus.adapters.llm.shutil.which", return_value="claude"),
            patch("talamus.adapters.llm.subprocess.run", return_value=fake),
        ):
            with self.assertRaises(EngineFailed) as ctx:
                _default_runner(["claude", "-p"], "hi")
        self.assertNotIsInstance(ctx.exception, EngineLimitReached)

    def test_engine_timeout_is_env_configurable(self) -> None:
        from unittest.mock import patch

        captured = {}

        def fake_run(args, **kwargs):
            captured.update(kwargs)
            import subprocess

            return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

        with (
            patch("talamus.adapters.llm.shutil.which", return_value="engine"),
            patch("talamus.adapters.llm.subprocess.run", side_effect=fake_run),
            patch.dict(os.environ, {"TALAMUS_ENGINE_TIMEOUT": "42"}),
        ):
            _default_runner(["engine"], "hi")
        self.assertEqual(captured["timeout"], 42)

    def test_poster_maps_http_429_to_limit_reached(self) -> None:
        import io
        import urllib.error
        from unittest.mock import patch

        from talamus.adapters.llm import _default_poster
        from talamus.errors import EngineLimitReached

        err = urllib.error.HTTPError(
            "https://api", 429, "Too Many Requests", hdrs=None, fp=io.BytesIO(b"")
        )
        with patch("talamus.adapters.llm.urllib.request.urlopen", side_effect=err):
            with self.assertRaises(EngineLimitReached):
                _default_poster("https://api", {}, {})

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

    def test_opencode_builds_a_read_only_run_command(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            captured["prompt"] = prompt
            return "ok"

        from talamus.adapters.llm import OpencodeCliProvider

        OpencodeCliProvider(runner=fake_runner).complete("ciao")
        # verified live 2026-07-02: `opencode run` reads the prompt from stdin
        # (no Windows argv limit) and `--agent plan` pins it read-only
        self.assertEqual(["opencode", "run", "--agent", "plan"], captured["args"])
        self.assertEqual("ciao", captured["prompt"])

    def test_opencode_applies_tier_model_and_variant(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            return "ok"

        from dataclasses import replace

        from talamus.adapters.llm import build_provider_for_task
        from talamus.config import TalamusConfig

        config = replace(
            TalamusConfig.default(),
            llm_provider="opencode",
            provider_models={"opencode": {"quality": "minimaxai/minimax-m2.7"}},
        )
        provider = build_provider_for_task("opencode", config, "quality", "high")
        provider._runner = fake_runner  # type: ignore[attr-defined]
        provider.complete("hi")
        self.assertIn("minimaxai/minimax-m2.7", captured["args"])
        self.assertIn("--variant", captured["args"])
        self.assertIn("high", captured["args"])

    def test_antigravity_builds_a_headless_print_command(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            captured["prompt"] = prompt
            return "ok"

        from talamus.adapters.llm import AntigravityCliProvider

        AntigravityCliProvider(model="gemini-3-pro", runner=fake_runner).complete("ciao")
        # verified live 2026-07-02: `agy -p ""` triggers print mode and the real
        # prompt travels on stdin (the same headless pattern as gemini-cli)
        self.assertEqual(["agy", "--model", "gemini-3-pro", "-p", ""], captured["args"])
        self.assertEqual("ciao", captured["prompt"])

    def test_new_provider_aliases_normalize(self) -> None:
        from talamus.adapters.llm import canonical_provider

        self.assertEqual(canonical_provider("agy"), "antigravity-cli")
        self.assertEqual(canonical_provider("antigravity"), "antigravity-cli")
        self.assertEqual(canonical_provider("opencode-cli"), "opencode")

    def test_build_provider_selects_the_new_types(self) -> None:
        from talamus.adapters.llm import AntigravityCliProvider, OpencodeCliProvider

        self.assertIsInstance(build_provider("opencode"), OpencodeCliProvider)
        self.assertIsInstance(build_provider("antigravity-cli"), AntigravityCliProvider)

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
