from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar

from talamus.jobs import JobRecord, JobStore
from talamus.paths import TalamusPaths
from talamus.services.result import ServiceResult

T = TypeVar("T")


@dataclass(frozen=True)
class JobItem:
    job_id: str
    kind: str
    state: str
    created_at: str
    updated_at: str
    payload: dict[str, Any]
    progress: dict[str, Any]
    result: dict[str, Any]
    error: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class JobLog:
    job_id: str
    log: str


def list_jobs(root: str | Path) -> ServiceResult[list[JobItem]]:
    try:
        records = _store(root).list()
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _job_store_error(exc)
    return ServiceResult(
        success=True,
        message="Jobs loaded",
        code="jobs_loaded",
        data=[_job_item(record) for record in records],
    )


def get_job(root: str | Path, job_id: str) -> ServiceResult[JobItem]:
    record_result: JobRecord | ServiceResult[JobItem] = _load_job(root, job_id)
    if isinstance(record_result, ServiceResult):
        return record_result
    return ServiceResult(
        success=True,
        message=f"Job {job_id!r} loaded",
        code="job_loaded",
        data=_job_item(record_result),
    )


def read_job_log(root: str | Path, job_id: str) -> ServiceResult[JobLog]:
    record_result: JobRecord | ServiceResult[JobLog] = _load_job(root, job_id)
    if isinstance(record_result, ServiceResult):
        return record_result
    try:
        log = _store(root).read_log(job_id)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _job_store_error(exc)
    return ServiceResult(
        success=True,
        message=f"Job {job_id!r} log loaded",
        code="job_log_loaded",
        data=JobLog(job_id=job_id, log=log),
    )


def cancel_job(root: str | Path, job_id: str) -> ServiceResult[JobItem]:
    record_result: JobRecord | ServiceResult[JobItem] = _load_job(root, job_id)
    if isinstance(record_result, ServiceResult):
        return record_result
    try:
        store = _store(root)
        if not store.cancel(job_id):
            return ServiceResult(
                success=False,
                message=f"Cannot cancel {job_id!r} (missing or already terminal)",
                code="job_not_cancellable",
            )
        cancelled = store.load(job_id)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _job_store_error(exc)
    if cancelled is None:
        return _not_found(job_id)
    return ServiceResult(
        success=True,
        message=f"Job {job_id!r} cancelled",
        code="job_cancelled",
        data=_job_item(cancelled),
    )


def _store(root: str | Path) -> JobStore:
    return JobStore(TalamusPaths(Path(root)))


def _load_job(root: str | Path, job_id: str) -> JobRecord | ServiceResult[T]:
    try:
        record = _store(root).load(job_id)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _job_store_error(exc)
    if record is None:
        return _not_found(job_id)
    return record


def _job_item(record: JobRecord) -> JobItem:
    return JobItem(
        job_id=record.job_id,
        kind=record.kind,
        state=record.state,
        created_at=record.created_at,
        updated_at=record.updated_at,
        payload=record.payload,
        progress=record.progress,
        result=record.result,
        error=record.error,
    )


def _not_found(job_id: str) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"No job {job_id!r}",
        code="job_not_found",
    )


def _job_store_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Job store error: {exc}",
        code="job_store_error",
    )
