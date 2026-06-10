"""Persistent job store — long operations survive crashes and resume (PRD 15.3).

A job is persisted *before* the first expensive call (11.3): the JSON record under
``.talamus/cache/jobs/`` holds the plan (payload), the progress (which items are
already done) and the state machine. A crash leaves a resumable record; a cancel
is cooperative (checked between items) and never corrupts already-written notes.

States: ``queued -> running -> completed|failed|cancelled`` with ``paused`` in
between; ``failed`` and ``paused`` can resume to ``running``.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from talamus.paths import TalamusPaths

JOB_KINDS = ("scan", "ingest", "verify", "ontology_induction", "eval", "export", "import")
JOB_STATES = ("queued", "running", "paused", "completed", "failed", "cancelled")
_TERMINAL = ("completed", "cancelled")
_LEGAL: dict[str, tuple[str, ...]] = {
    "queued": ("running", "cancelled"),
    "running": ("paused", "completed", "failed", "cancelled"),
    "paused": ("running", "cancelled"),
    "failed": ("running", "cancelled"),
    "completed": (),
    "cancelled": (),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class JobRecord:
    job_id: str
    kind: str
    state: str = "queued"
    created_at: str = ""
    updated_at: str = ""
    payload: dict = field(default_factory=dict)
    progress: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class JobStore:
    def __init__(self, paths: TalamusPaths) -> None:
        self._dir = paths.cache / "jobs"

    def _record_path(self, job_id: str) -> Path:
        return self._dir / f"{job_id}.json"

    def _log_path(self, job_id: str) -> Path:
        return self._dir / f"{job_id}.log"

    def create(self, kind: str, payload: dict | None = None) -> JobRecord:
        """Persist a new job BEFORE any expensive work starts."""
        if kind not in JOB_KINDS:
            raise ValueError(f"job kind must be one of {JOB_KINDS}, got {kind!r}")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        job_id = f"{kind}-{stamp}"
        suffix = 2
        while self._record_path(job_id).exists():
            job_id = f"{kind}-{stamp}-{suffix}"
            suffix += 1
        record = JobRecord(
            job_id=job_id,
            kind=kind,
            created_at=_now(),
            updated_at=_now(),
            payload=payload or {},
        )
        self.save(record)
        return record

    def save(self, record: JobRecord) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        record.updated_at = _now()
        path = self._record_path(record.job_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def load(self, job_id: str) -> JobRecord | None:
        path = self._record_path(job_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        known = {f for f in JobRecord.__dataclass_fields__}
        return JobRecord(**{k: v for k, v in data.items() if k in known})

    def list(self) -> list[JobRecord]:
        if not self._dir.exists():
            return []
        records = []
        for path in sorted(self._dir.glob("*.json")):
            record = self.load(path.stem)
            if record is not None:
                records.append(record)
        return records

    def transition(self, record: JobRecord, state: str) -> JobRecord:
        if state not in JOB_STATES:
            raise ValueError(f"unknown job state {state!r}")
        if state not in _LEGAL[record.state]:
            raise ValueError(f"illegal transition {record.state} -> {state}")
        record.state = state
        self.save(record)
        return record

    def cancel(self, job_id: str) -> bool:
        record = self.load(job_id)
        if record is None or record.state in _TERMINAL:
            return False
        record.state = "cancelled"
        self.save(record)
        self.log(job_id, "cancelled by user")
        return True

    def log(self, job_id: str, line: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._log_path(job_id).open("a", encoding="utf-8") as handle:
            handle.write(f"{_now()} {line}\n")

    def read_log(self, job_id: str) -> str:
        path = self._log_path(job_id)
        return path.read_text(encoding="utf-8") if path.is_file() else ""


def run_items(
    store: JobStore,
    record: JobRecord,
    items: list[str],
    handler: Callable[[str], None],
    stage: str = "",
) -> JobRecord:
    """Resumable item-by-item driver: already-done items are skipped, the done-set
    is persisted after every item, and an external cancel stops cooperatively.

    On a handler exception the job is marked ``failed`` (resumable) and the error
    re-raised — nothing already written is touched.
    """
    done: set[str] = set(record.progress.get("done_items", []))
    record = store.transition(record, "running")
    store.log(record.job_id, f"running: {len(items) - len(done)}/{len(items)} items to do")
    for item in items:
        if item in done:
            continue
        current = store.load(record.job_id)
        if current is not None and current.state == "cancelled":
            store.log(record.job_id, f"stopped at cancel ({len(done)}/{len(items)} done)")
            return current
        try:
            handler(item)
        except Exception as exc:
            record.error = f"{item}: {exc}"
            record.progress = {
                "done_items": sorted(done),
                "done": len(done),
                "total": len(items),
                "stage": stage,
            }
            record.state = "failed"
            store.save(record)
            store.log(record.job_id, f"failed on {item}: {exc}")
            raise
        done.add(item)
        progress = {
            "done_items": sorted(done),
            "done": len(done),
            "total": len(items),
            "stage": stage,
            "current": item,
        }
        # a cancel may have landed on disk WHILE the handler ran: never resurrect it
        current = store.load(record.job_id)
        if current is not None and current.state == "cancelled":
            current.progress = progress
            store.save(current)
            store.log(record.job_id, f"stopped at cancel ({len(done)}/{len(items)} done)")
            return current
        record.progress = progress
        store.save(record)
    record = store.transition(record, "completed")
    store.log(record.job_id, f"completed ({len(done)}/{len(items)})")
    return record
