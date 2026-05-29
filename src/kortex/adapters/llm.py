from __future__ import annotations

import shutil
import subprocess
from typing import Callable, Protocol


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str:
        ...


def _default_runner(args: list[str], prompt: str) -> str:
    executable = shutil.which(args[0])
    if executable is None:
        raise RuntimeError(f"command not found: {args[0]}")
    completed = subprocess.run(
        [executable, *args[1:]],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"LLM command failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


class ClaudeCliProvider:
    """Usa l'abbonamento via `claude -p` (modalità non interattiva)."""

    def __init__(self, runner: Callable[[list[str], str], str] = _default_runner) -> None:
        self._runner = runner

    def complete(self, prompt: str) -> str:
        return self._runner(["claude", "-p"], prompt)
