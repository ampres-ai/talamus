from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from talamus.adapters.llm import (
    ENGINE_COMMANDS,
    build_provider,
    canonical_provider,
    save_credential,
)
from talamus.config import TalamusConfig, load_config, load_or_default, save_config
from talamus.errors import ConfigError, EngineFailed, EngineLimitReached, EngineNotFound
from talamus.paths import TalamusPaths
from talamus.services.readiness import EngineReadiness, inspect_engines
from talamus.services.result import ServiceResult

# canonical_provider now lives in talamus.adapters.llm; re-exported here for callers
# that import it from this module.
__all__ = ["canonical_provider"]
_ENGINE_SETTING_FIELDS = ("llm_provider", "llm_model", "language")

# The actionable per-engine fix shown when a live probe fails (A1/D3). ONE source
# shared by CLI setup (`_verify_engine`) and the UI probe endpoint.
ENGINE_HINTS: dict[str, str] = {
    "opencode": (
        "connect a provider first: run `opencode auth login`, pick a provider and model\n"
        "     (free tiers exist), then re-run: talamus setup --engine opencode --verify-engine"
    ),
    "ollama": "is the ollama service running and a model pulled? try `ollama pull llama3.2`",
    "claude-cli": "run `claude` once to log in, then retry",
    "codex-cli": "run `codex` once to log in, then retry",
    "gemini-cli": "run `gemini` once to authenticate, then retry",
    "antigravity-cli": "run `agy` once to authenticate, then retry",
    "anthropic-api": "set ANTHROPIC_API_KEY, or save a key from the workbench Settings",
}

_PROBE_PROMPT = "Reply with exactly: ok"


def engine_hint(provider: str) -> str:
    """The actionable fix for a failing engine; generic fallback for unknown ones."""
    return ENGINE_HINTS.get(provider, "run `talamus doctor` for a full diagnosis")


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
    try:
        config = load_or_default(TalamusPaths(Path(root)).config_path)
    except (ConfigError, OSError, TypeError, ValueError) as exc:
        return _invalid_config_result(exc)
    invalid = _validate_engine_config(config)
    if invalid is not None:
        return invalid
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
    try:
        current = (
            load_config(paths.config_path)
            if paths.config_path.is_file()
            else TalamusConfig.default()
        )
    except (ConfigError, OSError, TypeError, ValueError) as exc:
        return _invalid_config_result(exc)
    invalid = _validate_engine_config(current)
    if invalid is not None:
        return invalid
    selected_provider = canonical_provider(current.llm_provider)
    if provider is not None and provider.strip():
        selected_provider = canonical_provider(provider)
    if selected_provider not in ENGINE_COMMANDS:
        return ServiceResult(
            success=False,
            message=f"Unsupported LLM provider: {selected_provider}",
            code="unsupported_provider",
        )
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


def probe_engine(root: str | Path, engine: str = "") -> ServiceResult[dict[str, object]]:
    """One tiny live completion against the provider (A1 for the UI): declare the
    engine working only after it answered. `limit_reached` is the honest v1 of
    "how much quota do I have left" — an on-demand probe that detects an
    exhausted limit the moment it bites, not a dashboard of provider internals
    we cannot see. Uses the brain's configured model when the probed provider
    is the configured one."""
    try:
        config = load_or_default(TalamusPaths(Path(root)).config_path)
    except (ConfigError, OSError, TypeError, ValueError) as exc:
        return ServiceResult(
            success=False,
            message=f"Invalid engine settings config: {exc}",
            code="engine_settings_invalid_config",
        )
    provider = canonical_provider(engine.strip() or config.llm_provider)
    if provider not in ENGINE_COMMANDS:
        return ServiceResult(
            success=False,
            message=f"Unsupported LLM provider: {provider}",
            code="unsupported_provider",
        )
    model = config.llm_model if canonical_provider(config.llm_provider) == provider else ""
    hint = engine_hint(provider)
    try:
        answer = build_provider(provider, model).complete(_PROBE_PROMPT)
    except EngineLimitReached as exc:
        return ServiceResult(
            success=False,
            message=f"engine '{provider}' NOT verified: {exc}",
            code="engine_limit_reached",
            data=_probe_failure(provider, exc, hint, limit_reached=True),
        )
    except (EngineFailed, EngineNotFound) as exc:
        return ServiceResult(
            success=False,
            message=f"engine '{provider}' NOT verified: {exc}",
            code="engine_not_verified",
            data=_probe_failure(provider, exc, hint, limit_reached=False),
        )
    return ServiceResult(
        success=True,
        message=f"engine '{provider}' verified",
        code="engine_verified",
        data={
            "engine": provider,
            "verified": True,
            "answer": answer.strip(),
            "hint": hint,
            "limit_reached": False,
        },
    )


def _probe_failure(
    provider: str, exc: Exception, hint: str, *, limit_reached: bool
) -> dict[str, object]:
    return {
        "engine": provider,
        "verified": False,
        "error": str(exc),
        "hint": hint,
        "limit_reached": limit_reached,
    }


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


def _validate_engine_config(config: TalamusConfig) -> ServiceResult[dict[str, str]] | None:
    for name in _ENGINE_SETTING_FIELDS:
        if not isinstance(getattr(config, name), str):
            return _invalid_config_result(TypeError(f"{name} must be a string"))
    return None


def _invalid_config_result(exc: Exception) -> ServiceResult[dict[str, str]]:
    return ServiceResult(
        success=False,
        message=f"Invalid engine settings config: {exc}",
        code="engine_settings_invalid_config",
    )
