from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol

from talamus.errors import EngineFailed, EngineNotFound


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str: ...


def _default_runner(args: list[str], prompt: str) -> str:
    executable = shutil.which(args[0])
    if executable is None:
        raise EngineNotFound(args[0])
    try:
        completed = subprocess.run(
            [executable, *args[1:]],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineFailed(f"engine timed out: {args[0]}") from exc
    if completed.returncode != 0:
        raise EngineFailed(f"LLM command failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _default_poster(url: str, headers: dict[str, str], payload: dict) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise EngineFailed(f"API request failed: {exc}") from exc


class ClaudeCliProvider:
    """CLI subscription via `claude -p` (non-interactive)."""

    def __init__(self, runner: Callable[[list[str], str], str] = _default_runner) -> None:
        self._runner = runner

    def complete(self, prompt: str) -> str:
        return self._runner(["claude", "-p"], prompt)


class CodexCliProvider:
    """OpenAI Codex CLI subscription via `codex exec` (prompt on stdin via `-`,
    dodging the Windows argv length limit). `codex exec` is an AGENT that can run
    shell commands, so we pin it down: read-only sandbox, no git-repo check —
    it must behave as a pure completion engine."""

    def __init__(self, runner: Callable[[list[str], str], str] = _default_runner) -> None:
        self._runner = runner

    def complete(self, prompt: str) -> str:
        return self._runner(
            ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "-"], prompt
        )


class GeminiCliProvider:
    """Google Gemini CLI subscription: `-p ""` triggers headless mode and the
    real prompt travels on stdin (the CLI appends -p to stdin input)."""

    def __init__(self, runner: Callable[[list[str], str], str] = _default_runner) -> None:
        self._runner = runner

    def complete(self, prompt: str) -> str:
        return self._runner(["gemini", "-p", ""], prompt)


class OllamaProvider:
    """Local model via the Ollama CLI — fully local, no subscription."""

    def __init__(
        self, model: str = "llama3", runner: Callable[[list[str], str], str] = _default_runner
    ) -> None:
        self._model = model
        self._runner = runner

    def complete(self, prompt: str) -> str:
        return self._runner(["ollama", "run", self._model], prompt)


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


def detect_engines() -> list[str]:
    """The engines actually usable on this machine, in preference order."""
    available = []
    for provider, command in (
        ("claude-cli", "claude"),
        ("codex-cli", "codex"),
        ("gemini-cli", "gemini"),
        ("ollama", "ollama"),
    ):
        if shutil.which(command):
            available.append(provider)
    available.append("anthropic-api")  # always offered (needs a key)
    return available


def build_provider(provider: str, model: str = "") -> LLMProvider:
    """Build the LLM provider selected in config (provider name + optional model)."""
    if provider == "claude-cli":
        return ClaudeCliProvider()
    if provider in ("codex-cli", "codex"):
        return CodexCliProvider()
    if provider in ("gemini-cli", "gemini"):
        return GeminiCliProvider()
    if provider == "ollama":
        return OllamaProvider(model or "llama3")
    if provider in ("anthropic-api", "api"):
        return AnthropicApiProvider(model or "claude-3-5-sonnet-latest")
    raise EngineNotFound(provider)
