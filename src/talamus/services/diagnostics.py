from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from talamus.adapters.llm import engine_command
from talamus.config import TalamusConfig, load_config
from talamus.domains import load_overview
from talamus.errors import TalamusError
from talamus.indexes import backend_info
from talamus.paths import TalamusPaths
from talamus.services.result import ServiceResult
from talamus.store import cache_is_current, reindex


@dataclass(frozen=True)
class DiagnosticCheck:
    check_id: str
    label: str
    status: str
    message: str
    detail: str = ""
    action: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosticsReport:
    root: str
    ok: bool
    storage_provider: str
    pdf_converter: str
    ocr_provider: str
    ocr_model: str
    llm_provider: str
    llm_status: str
    graph_provider: str
    search_provider: str
    notes: int
    index_backend: str
    index_bytes: int
    overview_built: bool
    overview_domains: int
    cache_current: bool
    checks: list[DiagnosticCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "ok": self.ok,
            "storage_provider": self.storage_provider,
            "pdf_converter": self.pdf_converter,
            "ocr_provider": self.ocr_provider,
            "ocr_model": self.ocr_model,
            "llm_provider": self.llm_provider,
            "llm_status": self.llm_status,
            "graph_provider": self.graph_provider,
            "search_provider": self.search_provider,
            "notes": self.notes,
            "index_backend": self.index_backend,
            "index_bytes": self.index_bytes,
            "overview_built": self.overview_built,
            "overview_domains": self.overview_domains,
            "cache_current": self.cache_current,
            "checks": [check.to_dict() for check in self.checks],
        }


def reindex_brain(root: str | Path) -> ServiceResult[dict[str, Any]]:
    """Rebuild the derived cache from the Markdown truth (UI parity for
    `talamus reindex`): re-reads notes and indexes, preserving provenance. The
    graph/index/overview are all derived, so this is always safe to run."""
    paths = TalamusPaths(Path(root))
    try:
        result = reindex(paths)
    except (OSError, ValueError, TalamusError) as exc:
        return ServiceResult(
            success=False,
            message=f"Reindex failed: {exc}",
            code="reindex_failed",
        )
    count = int(result.get("reindexed", 0)) if isinstance(result, dict) else 0
    return ServiceResult(
        success=True,
        message=f"Reindexed {count} notes — the cache is current.",
        code="reindexed",
        data={"reindexed": count},
    )


def inspect_diagnostics(root: str | Path) -> ServiceResult[DiagnosticsReport]:
    paths = TalamusPaths(Path(root))
    layout_checks = _layout_checks(paths)
    if not paths.config_path.exists():
        checks = [
            *layout_checks,
            DiagnosticCheck(
                "config",
                "Config",
                "error",
                "Talamus project is not initialized.",
                str(paths.config_path),
                "Run `talamus init`.",
            ),
        ]
        report = _report(paths, TalamusConfig.default(), checks)
        return ServiceResult(
            success=False,
            message="talamus project is not initialized; run `talamus init`",
            code="diagnostics_not_initialized",
            data=report,
        )
    try:
        config = load_config(paths.config_path)
    except TalamusError as exc:
        checks = [
            *layout_checks,
            DiagnosticCheck(
                "config",
                "Config",
                "error",
                "Config could not be loaded.",
                str(exc),
                "Fix talamus.json or run `talamus init` in a new brain.",
            ),
        ]
        report = _report(paths, TalamusConfig.default(), checks)
        return ServiceResult(
            success=False,
            message=f"config error: {paths.config_path}: {exc}",
            code="diagnostics_config_error",
            data=report,
        )
    report = _report(
        paths,
        config,
        [
            *layout_checks,
            DiagnosticCheck("config", "Config", "ok", "Config loaded.", str(paths.config_path)),
        ],
    )
    return ServiceResult(
        success=report.ok,
        message="Diagnostics completed" if report.ok else "Diagnostics found errors",
        code="diagnostics_ok" if report.ok else "diagnostics_failed",
        data=report,
    )


def _report(
    paths: TalamusPaths, config: TalamusConfig, initial_checks: list[DiagnosticCheck]
) -> DiagnosticsReport:
    llm_status, engine_check = _engine_check(config)
    notes = _note_count(paths)
    index = _backend_info(paths)
    overview = _overview(paths)
    cache_current = _cache_current(paths)
    checks = [
        *initial_checks,
        engine_check,
        _index_check(index),
        _overview_check(overview),
        _cache_check(cache_current),
    ]
    return DiagnosticsReport(
        root=str(paths.project_root.resolve()),
        ok=all(check.status != "error" for check in checks),
        storage_provider=config.storage_provider,
        pdf_converter=config.pdf_converter,
        ocr_provider=config.ocr_provider,
        ocr_model=config.ocr_model,
        llm_provider=config.llm_provider,
        llm_status=llm_status,
        graph_provider=config.graph_provider,
        search_provider=config.search_provider,
        notes=notes,
        index_backend=str(index.get("backend", "none")),
        index_bytes=int(index.get("bytes", 0) or 0),
        overview_built=bool(overview),
        overview_domains=len(overview),
        cache_current=cache_current,
        checks=checks,
    )


def _layout_checks(paths: TalamusPaths) -> list[DiagnosticCheck]:
    checks: list[DiagnosticCheck] = []
    for path in paths.required_directories():
        if not path.exists():
            checks.append(
                DiagnosticCheck(
                    "layout",
                    "Layout",
                    "error",
                    "Required directory is missing.",
                    str(path),
                    "Run `talamus init` or `talamus reindex`.",
                )
            )
        elif not path.is_dir():
            checks.append(
                DiagnosticCheck(
                    "layout",
                    "Layout",
                    "error",
                    "Required path is not a directory.",
                    str(path),
                    "Move the file away and run `talamus init` or `talamus reindex`.",
                )
            )
    return checks


def _engine_check(config: TalamusConfig) -> tuple[str, DiagnosticCheck]:
    command = engine_command(config.llm_provider)
    if command is None:
        return "ok", DiagnosticCheck("engine", "LLM", "ok", "No CLI command required.")
    executable = shutil.which(command)
    if executable:
        return "ok", DiagnosticCheck("engine", "LLM", "ok", "Engine command found.", executable)
    status = f"NOT on PATH ({command})"
    return status, DiagnosticCheck(
        "engine",
        "LLM",
        "warning",
        "Selected engine command was not found on PATH.",
        command,
        "Configure another engine or install the selected CLI.",
    )


def _note_count(paths: TalamusPaths) -> int:
    if not paths.notes.exists() or not paths.notes.is_dir():
        return 0
    return sum(1 for path in paths.notes.glob("*.md") if path.is_file())


def _backend_info(paths: TalamusPaths) -> dict[str, Any]:
    try:
        info = backend_info(paths)
    except (OSError, TypeError, ValueError, AttributeError):
        return {"backend": "none", "bytes": 0}
    return info if isinstance(info, dict) else {"backend": "none", "bytes": 0}


def _overview(paths: TalamusPaths) -> list[dict[str, Any]]:
    try:
        overview = load_overview(paths)
    except (OSError, TypeError, ValueError, AttributeError):
        return []
    if not isinstance(overview, list):
        return []
    return [entry for entry in overview if isinstance(entry, dict)]


def _cache_current(paths: TalamusPaths) -> bool:
    try:
        return cache_is_current(paths)
    except (OSError, TypeError, ValueError, AttributeError):
        return False


def _index_check(index: dict[str, Any]) -> DiagnosticCheck:
    backend = str(index.get("backend", "none"))
    bytes_count = int(index.get("bytes", 0) or 0)
    return DiagnosticCheck(
        "index",
        "Index",
        "ok" if backend != "none" else "warning",
        f"Index backend: {backend}.",
        f"{bytes_count} bytes",
        "Run `talamus reindex`." if backend == "none" else "",
    )


def _overview_check(overview: list[dict[str, Any]]) -> DiagnosticCheck:
    if overview:
        return DiagnosticCheck(
            "overview",
            "Overview",
            "ok",
            f"Overview built with {len(overview)} domains.",
        )
    return DiagnosticCheck(
        "overview",
        "Overview",
        "warning",
        "Overview is not built.",
        "",
        "Run `talamus overview`.",
    )


def _cache_check(current: bool) -> DiagnosticCheck:
    if current:
        return DiagnosticCheck("cache", "Cache", "ok", "Derived cache is current.")
    return DiagnosticCheck(
        "cache",
        "Cache",
        "warning",
        "Derived cache is stale.",
        "",
        "Run `talamus reindex`.",
    )
