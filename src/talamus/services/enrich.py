from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar

from talamus.config import load_or_default, resolve_language
from talamus.enrich import enrich_estimate, enrich_notes
from talamus.paths import TalamusPaths
from talamus.routing import Router
from talamus.services.result import ServiceResult

T = TypeVar("T")


@dataclass(frozen=True)
class EnrichPreview:
    root: str
    notes: int
    batches: int
    est_llm_calls: int
    requires_confirmation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def estimate_dict(self) -> dict[str, int]:
        return {
            "notes": self.notes,
            "batches": self.batches,
            "est_llm_calls": self.est_llm_calls,
        }


@dataclass(frozen=True)
class EnrichRunResult:
    root: str
    enriched: int
    skipped: int
    failed_batches: int
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_enrich(
    root: str | Path,
    router: Router,
    *,
    confirmed: bool = False,
) -> ServiceResult[EnrichPreview | EnrichRunResult]:
    root_path = Path(root)
    paths = TalamusPaths(root_path)
    try:
        preview = _preview(root_path)
        if preview.notes == 0:
            return ServiceResult(
                success=True,
                message="All notes already have symptom vocabulary",
                code="enrich_nothing_to_do",
                data=_run_result(root_path, {"enriched": 0, "skipped": 0, "failed_batches": 0}),
            )
        if not confirmed:
            return ServiceResult(
                success=True,
                message="Enrich confirmation required",
                code="enrich_confirmation_required",
                data=preview,
            )
        language = resolve_language(load_or_default(paths.config_path))
        report = enrich_notes(paths, router, language=language)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _enrich_error(exc)
    return ServiceResult(
        success=True,
        message="Enrich completed",
        code="enrich_completed",
        data=_run_result(root_path, report),
    )


def _preview(root: Path) -> EnrichPreview:
    estimate = enrich_estimate(TalamusPaths(root))
    notes = int(estimate["notes"])
    return EnrichPreview(
        root=str(root),
        notes=notes,
        batches=int(estimate["batches"]),
        est_llm_calls=int(estimate["est_llm_calls"]),
        requires_confirmation=notes > 0,
    )


def _run_result(root: Path, report: dict[str, Any]) -> EnrichRunResult:
    return EnrichRunResult(
        root=str(root),
        enriched=int(report.get("enriched", 0) or 0),
        skipped=int(report.get("skipped", 0) or 0),
        failed_batches=int(report.get("failed_batches", 0) or 0),
        raw=dict(report),
    )


def _enrich_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Enrich service error: {exc}",
        code="enrich_service_error",
    )
