from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar

from talamus.adapters.llm import LLMProvider
from talamus.correct import apply_correction, verify_batch, verify_note
from talamus.paths import TalamusPaths
from talamus.services.result import ServiceResult

T = TypeVar("T")


@dataclass(frozen=True)
class VerificationBatchResult:
    root: str
    checked: int
    ok: int
    stale: int
    corrections_proposed: int
    skipped: int
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationNoteResult:
    root: str
    title: str
    found: bool
    checked: bool
    ok: bool
    summary: str
    body: str
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationApplyResult:
    root: str
    title: str
    corrected: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_verification_batch(
    root: str | Path,
    llm: LLMProvider,
    *,
    only_stale: bool = False,
    source_filter: str | None = None,
) -> ServiceResult[VerificationBatchResult]:
    root_path = Path(root)
    try:
        report = verify_batch(
            TalamusPaths(root_path),
            llm,
            only_stale=only_stale,
            source_filter=source_filter,
        )
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _verification_error(exc)
    return ServiceResult(
        success=True,
        message="Verification batch completed",
        code="verification_batch_completed",
        data=_batch_result(root_path, report),
    )


def verify_single_note(
    root: str | Path,
    title: str,
    llm: LLMProvider,
) -> ServiceResult[VerificationNoteResult]:
    root_path = Path(root)
    try:
        report = verify_note(TalamusPaths(root_path), title, llm)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _verification_error(exc)
    return ServiceResult(
        success=True,
        message="Verification note checked",
        code="verification_note_checked",
        data=_note_result(root_path, title, report),
    )


def apply_note_correction(
    root: str | Path,
    title: str,
    llm: LLMProvider,
) -> ServiceResult[VerificationApplyResult]:
    root_path = Path(root)
    try:
        corrected = apply_correction(TalamusPaths(root_path), title, llm)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _verification_error(exc)
    return ServiceResult(
        success=True,
        message="Verification correction applied",
        code="verification_correction_applied",
        data=VerificationApplyResult(root=str(root_path), title=title, corrected=corrected),
    )


def _batch_result(root: Path, report: dict[str, Any]) -> VerificationBatchResult:
    return VerificationBatchResult(
        root=str(root),
        checked=_int_value(report.get("checked", 0)),
        ok=_int_value(report.get("ok", 0)),
        stale=_int_value(report.get("stale", 0)),
        corrections_proposed=_int_value(report.get("corrections_proposed", 0)),
        skipped=_int_value(report.get("skipped", 0)),
        raw=dict(report),
    )


def _note_result(root: Path, title: str, report: dict[str, Any]) -> VerificationNoteResult:
    return VerificationNoteResult(
        root=str(root),
        title=title,
        found=bool(report.get("found", False)),
        checked=bool(report.get("checked", False)),
        ok=bool(report.get("ok", True)),
        summary=str(report.get("summary", "")),
        body=str(report.get("body", "")),
        raw=dict(report),
    )


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected integer-compatible value, got {type(value).__name__}")


def _verification_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Verification service error: {exc}",
        code="verification_service_error",
    )
