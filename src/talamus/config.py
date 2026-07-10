from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from talamus.errors import ConfigError


@dataclass(frozen=True)
class TalamusConfig:
    storage_provider: str
    pdf_converter: str
    ocr_provider: str
    ocr_model: str
    llm_provider: str
    graph_provider: str
    search_provider: str
    llm_model: str = ""
    # The language the USER reads notes in (prose of title/summary/body).
    # Prompts are always English (cheap local models obey English best) and the
    # machine layer (relation surfaces, canonical aliases) is English-canonical.
    # Empty = auto-detect from the system locale.
    language: str = ""
    # P2 tiering overrides (empty = use the code defaults in talamus.routing).
    # task_tiers: {"<TaskClass value>": {"tier": "economy"|"quality", "effort": "low"|"high"}}
    task_tiers: dict[str, dict[str, str]] = field(default_factory=dict)
    # provider_models: {"<provider>": {"economy": "<model>", "quality": "<model>"}}
    provider_models: dict[str, dict[str, str]] = field(default_factory=dict)
    # Where the learned relation-type schema lives (the emergent ontology):
    # "global" (default) = one ontology shared across all brains (TALAMUS_HOME);
    # "brain" = the historical per-brain isolation. Evidence always stays per brain.
    ontology_scope: str = "global"

    @classmethod
    def default(cls) -> TalamusConfig:
        return cls(
            storage_provider="obsidian",
            # What is actually wired today: pypdf for PDFs, no OCR. P3 will wire a
            # real converter (e.g. docling) and OCR and flip these defaults.
            pdf_converter="pypdf",
            ocr_provider="none",
            ocr_model="none",
            llm_provider="claude-cli",
            graph_provider="deterministic-json",
            search_provider="builtin-bm25",
        )


def save_config(path: Path, config: TalamusConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")


def load_config(path: Path) -> TalamusConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config not found: {path}. Run `talamus init`.") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config {path}: {exc}") from exc
    try:
        config = TalamusConfig(**data)
    except TypeError as exc:
        raise ConfigError(f"Invalid config fields in {path}: {exc}") from exc
    empty = [
        name
        for name, value in asdict(config).items()
        if name not in ("llm_model", "language", "task_tiers", "provider_models")
        and not str(value).strip()
    ]
    if empty:
        raise ConfigError(f"Empty config fields in {path}: {', '.join(empty)}")
    return config


def _apply_env_overrides(config: TalamusConfig) -> TalamusConfig:
    """Override fields from TALAMUS_<FIELD> env vars, e.g. TALAMUS_LLM_PROVIDER=ollama."""
    overrides: dict[str, Any] = {
        field.name: os.environ[f"TALAMUS_{field.name.upper()}"]
        for field in fields(config)
        if os.environ.get(f"TALAMUS_{field.name.upper()}")
    }
    return replace(config, **overrides) if overrides else config


def load_or_default(path: Path) -> TalamusConfig:
    """Load config from disk if present (else defaults), then apply env overrides."""
    config = load_config(path) if path.is_file() else TalamusConfig.default()
    return _apply_env_overrides(config)


_LOCALE_LANGUAGES = {
    "it": "Italian",
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "nl": "Dutch",
}


def resolve_language(config: TalamusConfig) -> str:
    """The language notes are written in: explicit config wins, else the system
    locale, else English. Always an English language NAME ("Italian", ...) so it
    drops cleanly into English prompts."""
    if config.language.strip():
        return config.language.strip()
    import locale

    try:
        name = (locale.getlocale()[0] or "").strip()
    except ValueError:
        name = ""
    if name:
        prefix = name.split("_")[0].split("-")[0].lower()
        if prefix in _LOCALE_LANGUAGES:
            return _LOCALE_LANGUAGES[prefix]
        # Windows locales are already English names ("Italian_Italy")
        head = name.split("_")[0]
        if head.isalpha() and len(head) > 3:
            return head
    return "English"
