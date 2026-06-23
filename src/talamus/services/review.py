from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar

from talamus.paths import TalamusPaths
from talamus.review import ReviewItem, ReviewQueue
from talamus.services.result import ServiceResult

T = TypeVar("T")


@dataclass(frozen=True)
class ReviewEntry:
    item_id: str
    kind: str
    title: str
    status: str
    created_at: str
    resolved_at: str
    resolution: str
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_review_items(
    root: str | Path, status: str | None = "pending"
) -> ServiceResult[list[ReviewEntry]]:
    try:
        items = _queue(root).list(status=status)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _review_store_error(exc)
    return ServiceResult(
        success=True,
        message="Review items loaded",
        code="review_items_loaded",
        data=[_entry(item) for item in items],
    )


def get_review_item(root: str | Path, item_id: str) -> ServiceResult[ReviewEntry]:
    item_result: ReviewItem | ServiceResult[ReviewEntry] = _load_item(root, item_id)
    if isinstance(item_result, ServiceResult):
        return item_result
    return ServiceResult(
        success=True,
        message=f"Review item {item_id!r} loaded",
        code="review_item_loaded",
        data=_entry(item_result),
    )


def apply_review_item(root: str | Path, item_id: str) -> ServiceResult[ReviewEntry]:
    item_result: ReviewItem | ServiceResult[ReviewEntry] = _load_item(root, item_id)
    if isinstance(item_result, ServiceResult):
        return item_result
    if item_result.status != "pending":
        return _not_pending(item_id)
    if item_result.kind == "correction":
        from talamus.correct import apply_proposed_correction

        if not apply_proposed_correction(TalamusPaths(Path(root)), item_result.detail):
            return ServiceResult(
                success=False,
                message=f"Cannot apply correction for note {item_result.detail.get('title')!r}",
                code="review_correction_target_missing",
            )
    resolution = "correction written" if item_result.kind == "correction" else ""
    try:
        applied = _queue(root).apply(item_id, resolution=resolution)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _review_store_error(exc)
    if applied is None:
        return _not_pending(item_id)
    return ServiceResult(
        success=True,
        message=f"Review item {item_id!r} applied",
        code="review_item_applied",
        data=_entry(applied),
    )


def reject_review_item(
    root: str | Path, item_id: str, reason: str = ""
) -> ServiceResult[ReviewEntry]:
    item_result: ReviewItem | ServiceResult[ReviewEntry] = _load_item(root, item_id)
    if isinstance(item_result, ServiceResult):
        return item_result
    try:
        rejected = _queue(root).reject(item_id, reason)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _review_store_error(exc)
    if rejected is None:
        return _not_pending(item_id)
    return ServiceResult(
        success=True,
        message=f"Review item {item_id!r} rejected",
        code="review_item_rejected",
        data=_entry(rejected),
    )


def propose_review_note(
    root: str | Path, text: str, reason: str = ""
) -> ServiceResult[ReviewEntry]:
    """Add an uncertain note to the review queue (F10.4): it never lands directly in
    the notes. Used by the MCP propose_note tool."""
    title = text[:80] + ("…" if len(text) > 80 else "")
    try:
        item = _queue(root).add(
            "low_confidence_note",
            title,
            {"text": text, "reason": reason or "proposed by an agent"},
        )
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _review_store_error(exc)
    return ServiceResult(
        success=True,
        message=f"Proposed note in review: {item.item_id}",
        code="review_note_proposed",
        data=_entry(item),
    )


def _queue(root: str | Path) -> ReviewQueue:
    return ReviewQueue(TalamusPaths(Path(root)))


def _load_item(root: str | Path, item_id: str) -> ReviewItem | ServiceResult[T]:
    try:
        item = _queue(root).get(item_id)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _review_store_error(exc)
    if item is None:
        return ServiceResult(
            success=False,
            message=f"No review item {item_id!r}",
            code="review_item_not_found",
        )
    return item


def _entry(item: ReviewItem) -> ReviewEntry:
    return ReviewEntry(
        item_id=item.item_id,
        kind=item.kind,
        title=item.title,
        status=item.status,
        created_at=item.created_at,
        resolved_at=item.resolved_at,
        resolution=item.resolution,
        detail=item.detail,
    )


def _not_pending(item_id: str) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Review item {item_id!r} is not pending",
        code="review_item_not_pending",
    )


def _review_store_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Review queue error: {exc}",
        code="review_store_error",
    )
