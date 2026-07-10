from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import TYPE_CHECKING, NoReturn, Protocol

from talamus.errors import EngineFailed, EngineLimitReached, EngineNotFound

if TYPE_CHECKING:
    from talamus.config import TalamusConfig


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str: ...


# Dict order = auto-pick priority in choose_default_engine. gemini-cli sits last:
# Google deprecated the standalone CLI in favor of Antigravity (agy), so a machine
# with both must prefer agy; the adapter stays for installs that still use it.
ENGINE_COMMANDS: dict[str, str | None] = {
    "claude-cli": "claude",
    "codex-cli": "codex",
    "antigravity-cli": "agy",
    "opencode": "opencode",
    "ollama": "ollama",
    "gemini-cli": "gemini",
    "anthropic-api": None,
}

ENGINE_LABELS: dict[str, str] = {
    "claude-cli": "Claude CLI",
    "codex-cli": "Codex CLI",
    "antigravity-cli": "Antigravity CLI",
    "opencode": "opencode",
    "ollama": "Ollama",
    "gemini-cli": "Gemini CLI (deprecated)",
    "anthropic-api": "Anthropic API",
}

_ENGINE_COMMAND_ALIASES: dict[str, str | None] = {
    "codex": "codex",
    "gemini": "gemini",
    "api": None,
}


def engine_command(provider: str) -> str | None:
    return ENGINE_COMMANDS.get(provider, _ENGINE_COMMAND_ALIASES.get(provider, provider))


_PROVIDER_ALIASES: dict[str, str] = {
    "codex": "codex-cli",
    "gemini": "gemini-cli",
    "api": "anthropic-api",
    "agy": "antigravity-cli",
    "antigravity": "antigravity-cli",
    "opencode-cli": "opencode",
}


def canonical_provider(provider: str) -> str:
    """Normalize a provider name to its canonical form (e.g. 'codex' -> 'codex-cli')."""
    normalized = provider.strip()
    return _PROVIDER_ALIASES.get(normalized, normalized)


# Usage/rate-limit signatures across the supported engines (lowercase substrings).
# claude-cli: "usage limit", "session limit", "out of usage credits" (2026 phrasing);
# codex: "rate limit", 429; gemini: RESOURCE_EXHAUSTED / "quota";
# generic HTTP: 429 / too many requests.
_LIMIT_SIGNATURES = (
    "usage limit",
    "session limit",
    "usage credits",
    "out of credits",
    "rate limit",
    "resource_exhausted",
    "quota exceeded",
    "insufficient_quota",
    "too many requests",
    "429",
)


def _engine_timeout() -> int:
    """Hard per-call timeout in seconds (env TALAMUS_ENGINE_TIMEOUT, default 600).

    Read per call, not at import: covers the gemini-on-Windows hang and slow local
    models (measured: ~12.5% of gemma generations > 90 s) without freezing the product."""
    try:
        return max(1, int(os.environ.get("TALAMUS_ENGINE_TIMEOUT", "600")))
    except ValueError:
        return 600


def _raise_engine_failure(engine: str, detail: str) -> NoReturn:
    if any(sig in detail.lower() for sig in _LIMIT_SIGNATURES):
        raise EngineLimitReached(
            f"Usage/rate limit reached on {engine}: {detail} — wait for the reset, "
            "or switch engine (talamus setup / config llm_provider)."
        )
    raise EngineFailed(f"LLM command failed ({engine}): {detail}")


def _default_runner(args: list[str], prompt: str) -> str:
    executable = shutil.which(args[0])
    if executable is None:
        raise EngineNotFound(args[0])
    timeout = _engine_timeout()
    try:
        completed = subprocess.run(
            [executable, *args[1:]],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineFailed(
            f"engine timed out after {timeout}s: {args[0]} (tune with TALAMUS_ENGINE_TIMEOUT)"
        ) from exc
    if completed.returncode != 0:
        # CLI engines (e.g. `claude -p`) often write the real error to stdout and exit
        # non-zero with an empty stderr — surface whichever carries the reason so the
        # failure is actionable (e.g. a 401 means the CLI needs re-authentication).
        detail = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"exit code {completed.returncode}"
        )
        _raise_engine_failure(args[0], detail)
    return completed.stdout.strip()


def _default_poster(url: str, headers: dict[str, str], payload: dict) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise EngineLimitReached(
                f"Usage/rate limit reached on the API ({exc}) — wait for the reset, "
                "or switch engine."
            ) from exc
        raise EngineFailed(f"API request failed: {exc}") from exc
    except urllib.error.URLError as exc:
        raise EngineFailed(f"API request failed: {exc}") from exc


class ClaudeCliProvider:
    """CLI subscription via `claude -p` (non-interactive). ``model`` is a short CLI
    alias (e.g. "haiku", "opus"), passed as `--model` before `-p` (verified 2026-07-01);
    ``effort`` has no verified equivalent for this CLI today and is accepted but ignored."""

    def __init__(
        self,
        model: str = "",
        effort: str | None = None,
        runner: Callable[[list[str], str], str] = _default_runner,
    ) -> None:
        self._model = model
        self._effort = effort  # unused: no verified flag (see the tiering design doc)
        self._runner = runner

    def complete(self, prompt: str) -> str:
        args = ["claude"]
        if self._model:
            args += ["--model", self._model]
        args += ["-p"]
        return self._runner(args, prompt)


class CodexCliProvider:
    """OpenAI Codex CLI subscription via `codex exec` (prompt on stdin via `-`,
    dodging the Windows argv length limit). `codex exec` is an AGENT that can run
    shell commands, so we pin it down: read-only sandbox, no git-repo check —
    it must behave as a pure completion engine. Optional model via `-m`
    (config `llm_model`, e.g. a mini model for fast bulk ingest)."""

    def __init__(
        self,
        model: str = "",
        effort: str | None = None,
        runner: Callable[[list[str], str], str] = _default_runner,
    ) -> None:
        self._model = model
        self._effort = effort
        self._runner = runner

    def complete(self, prompt: str) -> str:
        args = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only"]
        if self._model:
            args += ["-m", self._model]
        if self._effort:
            args += ["-c", f"model_reasoning_effort={self._effort}"]
        return self._runner([*args, "-"], prompt)


class GeminiCliProvider:
    """Google Gemini CLI subscription: `-p ""` triggers headless mode and the
    real prompt travels on stdin (the CLI appends -p to stdin input).
    Gemini CLI is an AGENT too, so it gets the same treatment as codex:
    `--approval-mode plan` = read-only (no tool execution), `--skip-trust`
    because headless refuses to run in untrusted directories (rc=55).
    Optional model via `-m` (config `llm_model`, e.g. a flash model)."""

    def __init__(
        self,
        model: str = "",
        effort: str | None = None,
        runner: Callable[[list[str], str], str] = _default_runner,
    ) -> None:
        self._model = model
        self._effort = effort  # unused: no verified flag (see the tiering design doc)
        self._runner = runner

    def complete(self, prompt: str) -> str:
        args = ["gemini", "--skip-trust", "--approval-mode", "plan"]
        if self._model:
            args += ["-m", self._model]
        return self._runner([*args, "-p", ""], prompt)


class OpencodeCliProvider:
    """opencode subscription/credentials via `opencode run` (prompt on stdin —
    verified live 2026-07-02, dodging the Windows argv limit). opencode is an
    AGENT, so `--agent plan` pins it read-only: it must behave as a pure
    completion engine. ``model`` via `-m provider/model`; ``effort`` via
    `--variant` (opencode's provider-specific reasoning-effort knob)."""

    def __init__(
        self,
        model: str = "",
        effort: str | None = None,
        runner: Callable[[list[str], str], str] = _default_runner,
    ) -> None:
        self._model = model
        self._effort = effort
        self._runner = runner

    def complete(self, prompt: str) -> str:
        args = ["opencode", "run", "--agent", "plan"]
        if self._model:
            args += ["-m", self._model]
        if self._effort:
            args += ["--variant", self._effort]
        return self._runner(args, prompt)


class AntigravityCliProvider:
    """Google Antigravity CLI subscription via `agy -p ""` — print mode with the
    real prompt on stdin (the same headless pattern as gemini-cli; verified live
    2026-07-02). Antigravity is an AGENT whose tool permissions are denied by
    default in print mode, so it behaves as a completion engine. ``model`` via
    `--model`; ``effort`` has no known flag and is accepted but ignored."""

    def __init__(
        self,
        model: str = "",
        effort: str | None = None,
        runner: Callable[[list[str], str], str] = _default_runner,
    ) -> None:
        self._model = model
        self._effort = effort  # unused: no known flag
        self._runner = runner

    def complete(self, prompt: str) -> str:
        args = ["agy"]
        if self._model:
            args += ["--model", self._model]
        return self._runner([*args, "-p", ""], prompt)


class OllamaProvider:
    """Local model via Ollama — fully local, no subscription.

    Default path uses the CLI (`ollama run`). When `options` (e.g. num_predict
    to cap output, temperature=0 for determinism) or `think` is given, the HTTP
    /api/generate endpoint is used because the CLI does not expose them.
    `think=False` is essential for reasoning models (e.g. gemma3n/gemma4:e4b)
    used as a one-word judge: otherwise the reply budget is spent on hidden
    thinking tokens and `response` comes back empty."""

    def __init__(
        self,
        model: str = "llama3",
        runner: Callable[[list[str], str], str] = _default_runner,
        options: dict | None = None,
        poster: Callable[[str, dict[str, str], dict], dict] = _default_poster,
        think: bool | None = None,
    ) -> None:
        self._model = model
        self._runner = runner
        self._options = options
        self._poster = poster
        self._think = think

    def complete(self, prompt: str) -> str:
        if not self._options and self._think is None:
            return self._runner(["ollama", "run", self._model], prompt)
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        if not host.startswith("http"):
            host = f"http://{host}"
        payload: dict = {"model": self._model, "prompt": prompt, "stream": False}
        if self._options:
            payload["options"] = dict(self._options)
        if self._think is not None:
            payload["think"] = self._think
        data = self._poster(f"{host}/api/generate", {"content-type": "application/json"}, payload)
        return str(data.get("response", "")).strip()


class AnthropicApiProvider:
    """Anthropic Messages API via API key (env ANTHROPIC_API_KEY)."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-latest",
        poster: Callable[[str, dict[str, str], dict], dict] = _default_poster,
    ) -> None:
        self._model = model
        self._poster = poster

    def complete(self, prompt: str) -> str:
        key = os.environ.get("ANTHROPIC_API_KEY") or _stored_credential("anthropic_api_key")
        if not key:
            raise EngineNotFound(
                "anthropic-api (set ANTHROPIC_API_KEY, or save the key in Settings)"
            )
        data = self._poster(
            "https://api.anthropic.com/v1/messages",
            {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            {
                "model": self._model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        parts = data.get("content", [])
        return "".join(part.get("text", "") for part in parts).strip()


def _stored_credential(name: str) -> str:
    """Machine-level credential store: TALAMUS_HOME/credentials.json.

    Never inside a repo (our own scan redaction would flag it); env vars win."""
    from talamus.registry import talamus_home

    path = talamus_home() / "credentials.json"
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    return str(data.get(name, ""))


def stored_credential_present(name: str) -> bool:
    return bool(_stored_credential(name))


def save_credential(name: str, value: str) -> None:
    """Persist a credential machine-wide (used by the Settings view)."""
    from talamus.registry import talamus_home

    home = talamus_home()
    home.mkdir(parents=True, exist_ok=True)
    path = home / "credentials.json"
    data: dict = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data[name] = value
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_provider(provider: str, model: str = "") -> LLMProvider:
    """Build the LLM provider selected in config (provider name + optional model)."""
    if provider == "claude-cli":
        return ClaudeCliProvider()
    if provider in ("codex-cli", "codex"):
        return CodexCliProvider(model)
    if provider in ("gemini-cli", "gemini"):
        # Google discontinued the standalone gemini CLI in favor of Antigravity.
        # Keep the adapter for installs that still have the binary, but say so.
        print(
            "warning: the gemini CLI is deprecated by Google — switch this brain to"
            " 'antigravity-cli' (agy): talamus setup --engine antigravity-cli",
            file=sys.stderr,
        )
        return GeminiCliProvider(model)
    if provider in ("opencode", "opencode-cli"):
        return OpencodeCliProvider(model)
    if provider in ("antigravity-cli", "antigravity", "agy"):
        return AntigravityCliProvider(model)
    if provider == "ollama":
        return OllamaProvider(model or "llama3")
    if provider in ("anthropic-api", "api"):
        return AnthropicApiProvider(model or "claude-3-5-sonnet-latest")
    raise EngineNotFound(provider)


# Built-in tier -> model defaults per provider. A provider absent here (or a tier the
# table doesn't cover) falls back to the brain's single configured `llm_model` — this
# keeps providers with no natural "small vs large" split (e.g. ollama until the user
# pulls a second model) behaving as they do today for both tiers. Overridable per brain
# via config.provider_models. Aliases verified/standard as of 2026-07-02 (smoke-tested;
# codex also accepts model_reasoning_effort=xhigh on gpt-5.5 — see the spec).
_TIER_MODELS: dict[str, dict[str, str]] = {
    "claude-cli": {"economy": "haiku", "quality": "opus"},
    "codex-cli": {"economy": "gpt-5.4-mini", "quality": "gpt-5.5"},
    "gemini-cli": {"economy": "gemini-2.5-flash", "quality": "gemini-2.5-pro"},
    "anthropic-api": {
        "economy": "claude-3-5-haiku-latest",
        "quality": "claude-3-5-sonnet-latest",
    },
}


def _resolve_tiered_model(provider: str, config: TalamusConfig, tier: str) -> str:
    override = config.provider_models.get(provider, {})
    if tier in override:
        return override[tier]
    builtin = _TIER_MODELS.get(provider, {})
    if tier in builtin:
        return builtin[tier]
    return config.llm_model


def build_provider_for_task(
    provider: str, config: TalamusConfig, tier: str, effort: str
) -> LLMProvider:
    """Build the provider for one task's resolved (tier, effort) intent, within the
    single provider configured for the brain (tiering never switches providers)."""
    provider = canonical_provider(provider)
    model = _resolve_tiered_model(provider, config, tier)
    if provider == "claude-cli":
        return ClaudeCliProvider(model=model, effort=effort)
    if provider == "codex-cli":
        return CodexCliProvider(model=model, effort=effort)
    if provider == "gemini-cli":
        return GeminiCliProvider(model=model, effort=effort)
    if provider == "opencode":
        return OpencodeCliProvider(model=model, effort=effort)
    if provider == "antigravity-cli":
        return AntigravityCliProvider(model=model, effort=effort)
    if provider == "ollama":
        return OllamaProvider(model=model or "llama3")
    if provider == "anthropic-api":
        return AnthropicApiProvider(model=model or "claude-3-5-sonnet-latest")
    raise EngineNotFound(provider)
