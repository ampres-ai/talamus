from __future__ import annotations

import json
from typing import Any


def json_array(raw: str) -> list[Any]:
    """Extract one JSON array from model output using lenient JSON decoding."""
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON array in the model response")
    parsed = json.loads(raw[start : end + 1], strict=False)
    if not isinstance(parsed, list):
        raise ValueError("model JSON was not an array")
    return parsed


def json_object(raw: str) -> dict[str, Any]:
    """Extract one JSON object from model output using lenient JSON decoding."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in the model response")
    parsed = json.loads(raw[start : end + 1], strict=False)
    if not isinstance(parsed, dict):
        raise ValueError("model JSON was not an object")
    return parsed


def balanced_objects(raw: str) -> list[dict[str, Any]]:
    """Salvage complete top-level objects from truncated model JSON.

    Long model answers arrive truncated mid-JSON; an all-or-nothing parse
    silently drops EVERYTHING (measured on the book corpus: 'no duplicate
    concepts found' with 20+ real groups sitting in the raw answer)."""
    objects: list[dict[str, Any]] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(raw):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    parsed = json.loads(raw[start : i + 1], strict=False)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    objects.append(parsed)
                start = -1
    return objects
