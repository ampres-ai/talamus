from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from talamus.adapters.llm import (
    ENGINE_COMMANDS,
    ENGINE_LABELS,
    canonical_provider,
    engine_command,
    stored_credential_present,
)
from talamus.config import TalamusConfig, load_or_default
from talamus.domains import load_overview
from talamus.indexes import backend_info
from talamus.jobs import JobStore
from talamus.ontology_lab import schema_status
from talamus.paths import TalamusPaths
from talamus.registry import Registry, load_registry, talamus_home
from talamus.review import ReviewQueue
from talamus.scope import ResolvedBrain, resolve_brain
from talamus.services.integrations import mcp_installed
from talamus.store import cache_is_current


@dataclass(frozen=True)
class EngineReadiness:
    provider: str
    label: str
    command: str
    available: bool
    configured: bool
    needs_secret: bool
    status: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NextAction:
    action_id: str
    label: str
    detail: str
    target: str
    priority: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReadinessReport:
    root: str
    scope: str
    source: str
    config_exists: bool
    config_error: str
    selected_engine: str
    selected_model: str
    engines: list[EngineReadiness]
    registered_brains: int
    selected_brain: str
    notes: int
    sources: int
    reviews_pending: int
    jobs_active: int
    cache_current: bool
    index_backend: str
    index_bytes: int
    overview_built: bool
    overview_domains: int
    ontology_candidates: int
    mcp_installed: bool
    next_actions: list[NextAction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "scope": self.scope,
            "source": self.source,
            "config_exists": self.config_exists,
            "config_error": self.config_error,
            "selected_engine": self.selected_engine,
            "selected_model": self.selected_model,
            "engines": [engine.to_dict() for engine in self.engines],
            "registered_brains": self.registered_brains,
            "selected_brain": self.selected_brain,
            "notes": self.notes,
            "sources": self.sources,
            "reviews_pending": self.reviews_pending,
            "jobs_active": self.jobs_active,
            "cache_current": self.cache_current,
            "index_backend": self.index_backend,
            "index_bytes": self.index_bytes,
            "overview_built": self.overview_built,
            "overview_domains": self.overview_domains,
            "ontology_candidates": self.ontology_candidates,
            "mcp_installed": self.mcp_installed,
            "next_actions": [action.to_dict() for action in self.next_actions],
        }


def inspect_engines(selected_provider: str, selected_model: str = "") -> list[EngineReadiness]:
    engines: list[EngineReadiness] = []
    configured_provider = canonical_provider(selected_provider)
    for provider in ENGINE_COMMANDS:
        command = engine_command(provider)
        configured = provider == configured_provider
        available, needs_secret, status, detail = _engine_status(
            provider, command, configured, selected_model
        )
        engines.append(
            EngineReadiness(
                provider=provider,
                label=ENGINE_LABELS.get(provider, provider),
                command=command or "",
                available=available,
                configured=configured,
                needs_secret=needs_secret,
                status=status,
                detail=detail,
            )
        )
    return engines


def inspect_readiness(
    root: str | None = None,
    brain: str | None = None,
    use_global: bool = False,
    cwd: Path | None = None,
) -> ReadinessReport:
    resolved = _resolve_brain_safe(root, brain, use_global, cwd)
    paths = TalamusPaths(resolved.root)
    config_exists = paths.config_path.is_file()
    config_error = ""
    try:
        config = load_or_default(paths.config_path)
    except Exception as exc:
        config_error = str(exc)
        config = TalamusConfig.default()

    selected_raw = _config_text(config.llm_provider, TalamusConfig.default().llm_provider)
    selected_model = _config_text(config.llm_model, "")
    if selected_raw != config.llm_provider or selected_model != config.llm_model:
        config_error = config_error or "Invalid non-text config value"

    engines = inspect_engines(selected_raw, selected_model)
    registry = _load_registry_safe()
    notes = _count_notes(paths)
    sources = _count_sources(paths)
    reviews_pending = _pending_reviews(paths)
    jobs_active = _active_jobs(paths)
    current = _cache_current_safe(paths)
    index = _backend_info_safe(paths)
    overview = _load_overview_safe(paths)
    overview_domains = len(overview)
    ontology_candidates = _ontology_candidates(paths)
    selected_provider = canonical_provider(selected_raw)

    report = ReadinessReport(
        root=str(resolved.root),
        scope=resolved.scope,
        source=resolved.source,
        config_exists=config_exists,
        config_error=config_error,
        selected_engine=selected_provider,
        selected_model=selected_model,
        engines=engines,
        registered_brains=len(registry.brains),
        selected_brain=registry.selected,
        notes=notes,
        sources=sources,
        reviews_pending=reviews_pending,
        jobs_active=jobs_active,
        cache_current=current,
        index_backend=str(index.get("backend", "none")),
        index_bytes=int(index.get("bytes", 0)),
        overview_built=overview_domains > 0,
        overview_domains=overview_domains,
        ontology_candidates=ontology_candidates,
        mcp_installed=mcp_installed(paths.project_root),
        next_actions=[],
    )
    return _with_next_actions(report)


def _engine_status(
    provider: str, command: str | None, configured: bool, selected_model: str
) -> tuple[bool, bool, str, str]:
    model_detail = f"; model: {selected_model}" if configured and selected_model else ""
    if provider == "anthropic-api":
        available = bool(os.environ.get("ANTHROPIC_API_KEY")) or _credential_present_safe(
            "anthropic_api_key"
        )
        if available:
            return True, False, "ready", f"API key available{model_detail}"
        return (
            False,
            True,
            "needs_secret",
            "API key required",
        )
    if command is None:
        return False, False, "not_installed", "No command is registered for this provider"
    executable = shutil.which(command)
    if executable:
        return True, False, "ready", f"{executable}{model_detail}"
    return False, False, "not_installed", f"Command not found: {command}"


def _credential_present_safe(name: str) -> bool:
    try:
        return stored_credential_present(name)
    except (OSError, TypeError, ValueError, AttributeError):
        return False


def _config_text(value: object, fallback: str) -> str:
    return value if isinstance(value, str) else fallback


def _resolve_brain_safe(
    root: str | None,
    brain: str | None,
    use_global: bool,
    cwd: Path | None,
) -> ResolvedBrain:
    try:
        return resolve_brain(root, brain, use_global, cwd=cwd)
    except (OSError, TypeError, ValueError, AttributeError):
        home = talamus_home()
        if root is not None:
            return ResolvedBrain(Path(root).resolve(), "explicit", "--root")
        if brain is not None:
            return ResolvedBrain((home / brain).resolve(), "named", "--brain")
        if use_global:
            return ResolvedBrain((home / "default").resolve(), "global", "--global")
        start = (cwd or Path.cwd()).resolve()
        for directory in [start, *start.parents]:
            if (directory / "talamus.json").exists():
                return ResolvedBrain(directory, "project", "project-ancestor")
        return ResolvedBrain((home / "default").resolve(), "global", "default-global")


def _count_notes(paths: TalamusPaths) -> int:
    if not paths.notes.exists():
        return 0
    return sum(1 for path in paths.notes.glob("*.md") if path.is_file())


def _count_sources(paths: TalamusPaths) -> int:
    if not paths.raw.exists():
        return 0
    return sum(1 for path in paths.raw.rglob("*") if path.is_file())


def _pending_reviews(paths: TalamusPaths) -> int:
    try:
        return len(ReviewQueue(paths).list(status="pending"))
    except (OSError, TypeError, ValueError, AttributeError):
        return 0


def _active_jobs(paths: TalamusPaths) -> int:
    try:
        return sum(
            1 for job in JobStore(paths).list() if job.state in ("queued", "running", "paused")
        )
    except (OSError, TypeError, ValueError, AttributeError):
        return 0


def _cache_current_safe(paths: TalamusPaths) -> bool:
    try:
        return cache_is_current(paths)
    except (OSError, TypeError, ValueError, AttributeError, json.JSONDecodeError):
        return False


def _backend_info_safe(paths: TalamusPaths) -> dict[str, Any]:
    try:
        info = backend_info(paths)
    except (OSError, TypeError, ValueError, AttributeError):
        return {"backend": "none", "bytes": 0}
    if not isinstance(info, dict):
        return {"backend": "none", "bytes": 0}
    return info


def _load_overview_safe(paths: TalamusPaths) -> list[dict[str, Any]]:
    try:
        overview = load_overview(paths)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return []
    if not isinstance(overview, list):
        return []
    return [entry for entry in overview if isinstance(entry, dict)]


def _ontology_candidates(paths: TalamusPaths) -> int:
    try:
        status = schema_status(paths)
    except (OSError, TypeError, ValueError, AttributeError, json.JSONDecodeError):
        return 0
    types = status.get("types") if isinstance(status, dict) else None
    if not isinstance(types, dict):
        return 0
    return int(types.get("candidate", 0) or 0)


def _load_registry_safe() -> Registry:
    try:
        return load_registry()
    except (OSError, TypeError, ValueError, AttributeError):
        return Registry()


def _with_next_actions(report: ReadinessReport) -> ReadinessReport:
    return replace(report, next_actions=_next_actions(report))


def _next_actions(report: ReadinessReport) -> list[NextAction]:
    if not report.config_exists:
        return [
            NextAction(
                "open_brain",
                "Open brain",
                "Open an existing Talamus brain.",
                "brains",
                10,
            ),
            NextAction(
                "try_demo",
                "Try demo",
                "Create and inspect the local demo brain.",
                "demo",
                20,
            ),
            NextAction(
                "create_brain",
                "Create brain",
                "Initialize a new Talamus brain in this workspace.",
                "brains",
                30,
            ),
        ]

    actions: list[NextAction] = []
    if not _selected_engine_available(report):
        actions.append(
            NextAction(
                "configure_engine",
                "Configure engine",
                f"Selected engine {report.selected_engine!r} is not available.",
                "system",
                10,
            )
        )
    if report.jobs_active:
        actions.append(
            NextAction(
                "review_jobs",
                "Review jobs",
                "Resume, cancel or inspect active import jobs.",
                "import",
                20,
            )
        )
    if report.reviews_pending:
        actions.append(
            NextAction(
                "review_queue",
                "Review queue",
                "Apply or reject pending review items.",
                "review",
                30,
            )
        )
    if report.ontology_candidates:
        actions.append(
            NextAction(
                "review_ontology",
                "Review ontology candidates",
                "Promote or reject candidate relation types.",
                "ontology",
                35,
            )
        )
    if report.notes == 0:
        actions.append(
            NextAction(
                "import_content",
                "Import content",
                "Add files, folders, URLs or notes to this brain.",
                "import",
                40,
            )
        )
    if report.notes and not report.overview_built:
        actions.append(
            NextAction(
                "build_overview",
                "Build overview",
                "Generate the domain overview for navigation and routed ask.",
                "ontology",
                50,
            )
        )
    if report.notes and report.cache_current:
        actions.append(
            NextAction(
                "ask_question",
                "Ask question",
                "Ask a cited question against this brain.",
                "ask",
                60,
            )
        )
    if not report.cache_current:
        actions.append(
            NextAction(
                "reindex",
                "Reindex",
                "Rebuild derived indexes and cache metadata.",
                "system",
                70,
            )
        )
    return actions


def _selected_engine_available(report: ReadinessReport) -> bool:
    for engine in report.engines:
        if engine.configured:
            return engine.available
    return False
