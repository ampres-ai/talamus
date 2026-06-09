"""Talamus exception hierarchy. Each error carries an actionable, user-facing message."""

from __future__ import annotations

from pathlib import Path


class TalamusError(Exception):
    """Base class for all Talamus errors."""


class BrainNotInitialized(TalamusError):
    """The target directory has no Talamus brain yet."""

    def __init__(self, root: Path | str) -> None:
        super().__init__(f"No Talamus brain at '{root}'. Run `talamus init` to create one.")


class ConfigError(TalamusError):
    """The config file is missing or invalid."""


class EngineNotFound(TalamusError):
    """The configured LLM engine executable is not on PATH."""

    def __init__(self, command: str) -> None:
        super().__init__(
            f"LLM engine '{command}' not found on PATH. "
            "Install it, or configure another engine in talamus.json."
        )


class EngineFailed(TalamusError):
    """The LLM engine ran but returned an error."""


class SourceNotFound(TalamusError):
    """An ingest source file does not exist."""

    def __init__(self, path: Path | str) -> None:
        super().__init__(f"Source file not found: {path}")
