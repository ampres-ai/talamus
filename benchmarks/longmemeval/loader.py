"""Load and minimally validate the official LongMemEval_S dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_RELEASE_URL = "https://github.com/xiaowu0162/LongMemEval"
_REQUIRED_FIELDS = {
    "question_id": str,
    "question_type": str,
    "question": str,
    # the official file carries some gold answers as numbers (temporal
    # reasoning) — anything scalar is accepted and normalized to str below
    "answer": (str, int, float),
    "haystack_sessions": list,
    "haystack_dates": list,
    "question_date": str,
    "answer_session_ids": list,
}


def _invalid(index: int, detail: str) -> ValueError:
    return ValueError(f"Invalid LongMemEval item at index {index}: {detail}")


def _validate_item(item: Any, index: int) -> dict:
    if not isinstance(item, dict):
        raise _invalid(index, "expected a JSON object")

    for field, expected_type in _REQUIRED_FIELDS.items():
        if field not in item:
            raise _invalid(index, f"missing required field '{field}'")
        if not isinstance(item[field], expected_type):
            label = getattr(expected_type, "__name__", str(expected_type))
            raise _invalid(index, f"field '{field}' must be a {label}")
    item["answer"] = str(item["answer"])

    sessions = item["haystack_sessions"]
    dates = item["haystack_dates"]
    if len(dates) != len(sessions):
        raise _invalid(index, "haystack_dates must have one entry per haystack session")
    if not all(isinstance(date, str) for date in dates):
        raise _invalid(index, "every haystack date must be a string")

    for session_index, session in enumerate(sessions):
        if not isinstance(session, list):
            raise _invalid(index, f"haystack session {session_index} must be a list")
        for turn_index, turn in enumerate(session):
            if not isinstance(turn, dict):
                raise _invalid(
                    index,
                    f"turn {turn_index} in haystack session {session_index} must be an object",
                )
            if not isinstance(turn.get("role"), str) or not isinstance(turn.get("content"), str):
                raise _invalid(
                    index,
                    f"turn {turn_index} in haystack session {session_index} requires string "
                    "role and content fields",
                )

    # Preserve unknown official fields so newer dataset releases remain usable.
    return item


def load_dataset(path: Path) -> list[dict]:
    """Parse a local LongMemEval_S JSON file without downloading anything."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"LongMemEval dataset not found at {path}. Download longmemeval_s.json from the "
            f"official LongMemEval release ({_RELEASE_URL}) and place it in "
            ".bench-data/longmemeval/."
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Invalid LongMemEval dataset: expected a top-level JSON list")
    return [_validate_item(item, index) for index, item in enumerate(data)]
