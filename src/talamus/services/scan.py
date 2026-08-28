from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

from talamus.errors import TalamusError
from talamus.jobs import JobStore
from talamus.paths import TalamusPaths
from talamus.routing import Router
from talamus.scan import ScanPlan, build_plan, execute_plan, scan_job_payload
from talamus.services.result import ServiceResult

T = TypeVar("T")


@dataclass(frozen=True)
class ScanPreview:
    brain_root: str
    target_root: str
    profile: str
    files: int
    skipped: int
    total_bytes: int
    est_tokens: int
    est_llm_calls: int
    secret_files: tuple[str, ...]
    plan: ScanPlan

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScanActionResult:
    brain_root: str
    target_root: str
    state: str
    files: int
    notes_written: int
    job_id: str
    failed: tuple[dict[str, Any], ...]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preview_scan(
    brain_root: str | Path,
    target: str | Path,
    *,
    profile: str = "all",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_files: int | None = None,
) -> ServiceResult[ScanPreview]:
    try:
        preview = _build_preview(
            Path(brain_root),
            Path(target),
            profile=profile,
            include=include,
            exclude=exclude,
            max_files=max_files,
        )
    except TalamusError as exc:
        return ServiceResult(
            success=False,
            message=f"Scan failed: {exc}",
            code="scan_failed",
        )
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _scan_error(exc)
    return ServiceResult(
        success=True,
        message="Scan preview ready",
        code="scan_preview_ready",
        data=preview,
    )


def run_scan(
    brain_root: str | Path,
    target: str | Path,
    router: Router,
    *,
    profile: str = "all",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_files: int | None = None,
    confirmed: bool = False,
    background: bool = False,
    allow_secrets: bool = False,
) -> ServiceResult[ScanPreview | ScanActionResult]:
    brain_path = Path(brain_root)
    try:
        preview = _build_preview(
            brain_path,
            Path(target),
            profile=profile,
            include=include,
            exclude=exclude,
            max_files=max_files,
        )
        if not confirmed and not background:
            return ServiceResult(
                success=True,
                message="Scan confirmation required",
                code="scan_confirmation_required",
                data=preview,
            )
        if preview.secret_files and not allow_secrets:
            return ServiceResult(
                success=False,
                message="Scan blocked because likely secrets were detected",
                code="scan_secrets_blocked",
                data=preview,
            )
        if not preview.files:
            return ServiceResult(
                success=True,
                message="Nothing to scan",
                code="scan_nothing_to_scan",
                data=_action_result(
                    brain_path,
                    preview.target_root,
                    {
                        "job_id": "",
                        "state": "empty",
                        "files": 0,
                        "notes_written": 0,
                        "failed": [],
                    },
                ),
            )
        if background:
            record = JobStore(TalamusPaths(brain_path)).create(
                "scan",
                payload=scan_job_payload(preview.plan, allow_secrets=allow_secrets),
            )
            return ServiceResult(
                success=True,
                message="Scan job queued",
                code="scan_queued",
                data=_action_result(
                    brain_path,
                    preview.target_root,
                    {
                        "job_id": record.job_id,
                        "state": record.state,
                        "files": preview.files,
                        "notes_written": 0,
                        "failed": [],
                    },
                ),
            )
        report = cast(
            dict[str, Any],
            execute_plan(
                TalamusPaths(brain_path),
                preview.plan,
                router,
                allow_secrets=allow_secrets,
            ),
        )
    except TalamusError as exc:
        return ServiceResult(
            success=False,
            message=f"Scan failed: {exc}",
            code="scan_failed",
        )
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _scan_error(exc)
    return ServiceResult(
        success=True,
        message="Scan completed",
        code="scan_completed",
        data=_action_result(brain_path, preview.target_root, report),
    )


def _build_preview(
    brain_root: Path,
    target: Path,
    *,
    profile: str,
    include: list[str] | None,
    exclude: list[str] | None,
    max_files: int | None,
) -> ScanPreview:
    plan = build_plan(
        target,
        profile=profile,
        include=include,
        exclude=exclude,
        max_files=max_files,
    )
    secret_files = tuple(sorted({str(finding["path"]) for finding in plan.secret_flags}))
    return ScanPreview(
        brain_root=str(brain_root),
        target_root=plan.root,
        profile=plan.profile,
        files=len(plan.included),
        skipped=len(plan.excluded),
        total_bytes=plan.total_bytes,
        est_tokens=plan.est_tokens,
        est_llm_calls=plan.est_llm_calls,
        secret_files=secret_files,
        plan=plan,
    )


def _action_result(
    brain_root: Path,
    target_root: str,
    result: dict[str, Any],
) -> ScanActionResult:
    return ScanActionResult(
        brain_root=str(brain_root),
        target_root=target_root,
        state=str(result.get("state", "")),
        files=_int_value(result.get("files", 0)),
        notes_written=_int_value(result.get("notes_written", 0)),
        job_id=str(result.get("job_id", "")),
        failed=_failed_items(result.get("failed", [])),
        raw=dict(result),
    )


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected integer-compatible value, got {type(value).__name__}")


def _failed_items(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def _scan_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Scan service error: {exc}",
        code="scan_service_error",
    )
