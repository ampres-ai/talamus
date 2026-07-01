from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

from talamus.adapters.llm import LLMProvider
from talamus.errors import TalamusError
from talamus.ingest import estimate_chunks, ingest_path, ingest_text
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.services.result import ServiceResult
from talamus.sources import is_url

T = TypeVar("T")


@dataclass(frozen=True)
class IngestPreview:
    root: str
    target: str
    target_type: str
    source: str
    chars: int
    chunks: int
    est_llm_calls: int
    est_input_tokens: int
    requires_confirmation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IngestRunResult:
    root: str
    target: str
    notes_written: int
    source: str
    files: int | None
    skipped: int | None
    chunks: int | None
    job_id: str | None
    state: str | None
    failed: tuple[dict[str, Any], ...]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preview_ingest(root: str | Path, target: str) -> ServiceResult[IngestPreview]:
    root_path = Path(root)
    try:
        preview = _build_preview(root_path, target)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ingestion_error(exc)
    return ServiceResult(
        success=True,
        message="Ingest preview ready",
        code="ingest_preview_ready",
        data=preview,
    )


def run_ingest(
    root: str | Path,
    target: str,
    llm: LLMProvider,
    *,
    confirmed: bool = False,
) -> ServiceResult[IngestPreview | IngestRunResult]:
    root_path = Path(root)
    try:
        preview = _build_preview(root_path, target)
        if preview.requires_confirmation and not confirmed:
            return ServiceResult(
                success=True,
                message="Ingest confirmation required",
                code="ingest_confirmation_required",
                data=preview,
            )
        result = cast(
            dict[str, Any], ingest_path(TalamusPaths(root_path), target, StaticRouter(llm))
        )
    except TalamusError as exc:
        return ServiceResult(
            success=False,
            message=f"Ingest failed: {exc}",
            code="ingest_failed",
        )
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ingestion_error(exc)
    return ServiceResult(
        success=True,
        message="Ingest completed",
        code="ingest_completed",
        data=_run_result(root_path, target, result),
    )


def ingest_raw_text(
    root: str | Path,
    text: str,
    llm: LLMProvider,
    *,
    name: str = "insight",
) -> ServiceResult[IngestRunResult]:
    """Compile a raw text string into brain notes (no file on disk). Used by the
    MCP remember/ingest_text tools."""
    root_path = Path(root)
    try:
        result = cast(
            dict[str, Any],
            ingest_text(TalamusPaths(root_path), text, StaticRouter(llm), name=name),
        )
    except TalamusError as exc:
        return ServiceResult(success=False, message=f"Ingest failed: {exc}", code="ingest_failed")
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ingestion_error(exc)
    return ServiceResult(
        success=True,
        message="Text ingested",
        code="text_ingested",
        data=_run_result(root_path, name, result),
    )


def _build_preview(root: Path, target: str) -> IngestPreview:
    if is_url(target):
        return _preview_for_non_file(root, target, "url", target)
    target_path = Path(target)
    if target_path.is_dir():
        return _preview_for_non_file(root, target, "directory", str(target_path))
    if not target_path.is_file():
        raise FileNotFoundError(target)
    estimate = estimate_chunks(TalamusPaths(root), target_path)
    return IngestPreview(
        root=str(root),
        target=target,
        target_type="file",
        source=str(estimate["source"]),
        chars=int(estimate["chars"]),
        chunks=int(estimate["chunks"]),
        est_llm_calls=int(estimate["est_llm_calls"]),
        est_input_tokens=int(estimate["est_input_tokens"]),
        requires_confirmation=int(estimate["chunks"]) > 3,
    )


def _preview_for_non_file(root: Path, target: str, target_type: str, source: str) -> IngestPreview:
    return IngestPreview(
        root=str(root),
        target=target,
        target_type=target_type,
        source=source,
        chars=0,
        chunks=0,
        est_llm_calls=0,
        est_input_tokens=0,
        requires_confirmation=False,
    )


def _run_result(root: Path, target: str, result: dict[str, Any]) -> IngestRunResult:
    return IngestRunResult(
        root=str(root),
        target=target,
        notes_written=int(result.get("notes_written", 0) or 0),
        source=str(result.get("source", "")),
        files=_optional_int(result.get("files")),
        skipped=_optional_int(result.get("skipped")),
        chunks=_optional_int(result.get("chunks")),
        job_id=_optional_str(result.get("job_id")),
        state=_optional_str(result.get("state")),
        failed=_failed_items(result.get("failed", [])),
        raw=dict(result),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected integer-compatible value, got {type(value).__name__}")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _failed_items(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def _ingestion_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Ingest service error: {exc}",
        code="ingest_service_error",
    )
