"""Persistent review queue — uncertain changes wait for a human.

Items live one-per-file under ``.talamus/cache/review/``. Applying or rejecting
never deletes the item: the decision is recorded (rejections stay logged, F7.6).
The *effect* of applying depends on the item kind and is wired by the producing
feature (corrections in M7, ontology candidates in M5, scan safety in M3).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from talamus.paths import TalamusPaths

REVIEW_KINDS = (
    "duplicate_concept",
    "correction",
    "ontology_candidate",
    "property",
    "stale_source",
    "low_confidence_note",
    "scan_safety",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ReviewItem:
    item_id: str
    kind: str
    title: str
    status: str = "pending"
    created_at: str = ""
    resolved_at: str = ""
    resolution: str = ""
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ReviewQueue:
    def __init__(self, paths: TalamusPaths) -> None:
        self._dir = paths.cache / "review"

    def _path(self, item_id: str) -> Path:
        return self._dir / f"{item_id}.json"

    def add(self, kind: str, title: str, detail: dict | None = None) -> ReviewItem:
        if kind not in REVIEW_KINDS:
            raise ValueError(f"review kind must be one of {REVIEW_KINDS}, got {kind!r}")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        item_id = f"{kind}-{stamp}"
        suffix = 2
        while self._path(item_id).exists():
            item_id = f"{kind}-{stamp}-{suffix}"
            suffix += 1
        item = ReviewItem(
            item_id=item_id, kind=kind, title=title, created_at=_now(), detail=detail or {}
        )
        self._save(item)
        return item

    def _save(self, item: ReviewItem) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(item.item_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(item.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def get(self, item_id: str) -> ReviewItem | None:
        path = self._path(item_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        known = {f for f in ReviewItem.__dataclass_fields__}
        return ReviewItem(**{k: v for k, v in data.items() if k in known})

    def list(self, status: str | None = None) -> list[ReviewItem]:
        if not self._dir.exists():
            return []
        items = []
        for path in sorted(self._dir.glob("*.json")):
            item = self.get(path.stem)
            if item is not None and (status is None or item.status == status):
                items.append(item)
        return items

    def apply(self, item_id: str, resolution: str = "") -> ReviewItem | None:
        item = self.get(item_id)
        if item is None or item.status != "pending":
            return None
        item.status = "applied"
        item.resolved_at = _now()
        item.resolution = resolution or "applied"
        self._save(item)
        return item

    def reject(self, item_id: str, reason: str = "") -> ReviewItem | None:
        """Rejections are recorded, never deleted (F7.6)."""
        item = self.get(item_id)
        if item is None or item.status != "pending":
            return None
        item.status = "rejected"
        item.resolved_at = _now()
        item.resolution = reason or "rejected"
        self._save(item)
        return item
