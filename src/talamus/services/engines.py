from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from talamus.adapters.llm import save_credential
from talamus.config import TalamusConfig, load_or_default, save_config
from talamus.paths import TalamusPaths
from talamus.services.readiness import EngineReadiness, inspect_engines
from talamus.services.result import ServiceResult

_ALIASES: dict[str, str] = {
    "codex": "codex-cli",
    "gemini": "gemini-cli",
    "api": "anthropic-api",
}


def canonical_provider(provider: str) -> str:
    normalized = provider.strip()
    return _ALIASES.get(normalized, normalized)


def list_engines(selected_provider: str = "", selected_model: str = "") -> list[EngineReadiness]:
    selected = canonical_provider(selected_provider or TalamusConfig.default().llm_provider)
    return inspect_engines(selected, selected_model)


def choose_default_engine() -> str:
    """Pick the first installed CLI engine; fall back to claude-cli."""
    for engine in list_engines():
        if engine.provider == "anthropic-api":
            continue
        if engine.available:
            return engine.provider
    return TalamusConfig.default().llm_provider


def load_engine_settings(root: str | Path) -> ServiceResult[dict[str, str]]:
    config = load_or_default(TalamusPaths(Path(root)).config_path)
    return ServiceResult(
        success=True,
        message="Engine settings loaded",
        code="engine_settings_loaded",
        data=_engine_settings(config),
    )


def update_engine_settings(
    root: str | Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    language: str | None = None,
) -> ServiceResult[dict[str, str]]:
    paths = TalamusPaths(Path(root))
    current = load_or_default(paths.config_path)
    selected_provider = canonical_provider(current.llm_provider)
    if provider is not None and provider.strip():
        selected_provider = canonical_provider(provider)
    updated = replace(
        current,
        llm_provider=selected_provider,
        llm_model=current.llm_model if model is None else model,
        language=current.language if language is None else language,
    )
    save_config(paths.config_path, updated)
    return ServiceResult(
        success=True,
        message="Engine settings saved",
        code="engine_settings_saved",
        data=_engine_settings(updated),
    )


def save_anthropic_api_key(api_key: str) -> ServiceResult[dict[str, object]]:
    secret = api_key.strip()
    if not secret:
        return ServiceResult(
            success=False,
            message="Anthropic API key is empty",
            code="anthropic_api_key_empty",
            data={"credential": "anthropic_api_key", "saved": False},
        )
    save_credential("anthropic_api_key", secret)
    return ServiceResult(
        success=True,
        message="Anthropic API key saved",
        code="anthropic_api_key_saved",
        data={"credential": "anthropic_api_key", "saved": True},
    )


def _engine_settings(config: TalamusConfig) -> dict[str, str]:
    return {
        "llm_provider": canonical_provider(config.llm_provider),
        "llm_model": config.llm_model,
        "language": config.language,
    }
