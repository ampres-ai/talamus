"""Bitemporal history: past versions of a note are kept, never overwritten.

`write_note_json` appends the prior version to `.talamus/cache/history/<id>.jsonl`
before merging in a change, so you never lose what a note said before — and can ask
what it looked like at a point in time.
"""

from __future__ import annotations

import json

from talamus.naming import note_slug
from talamus.paths import TalamusPaths
from talamus.store import load_notes


def _note_id_for_title(paths: TalamusPaths, title: str) -> str | None:
    for note in load_notes(paths):
        if note.title.lower() == title.lower():
            return note.note_id
    return None


def note_history(paths: TalamusPaths, title: str) -> list[dict]:
    """All known versions of a note, oldest first, including the current one."""
    note_id = _note_id_for_title(paths, title)
    if note_id is None:
        return []
    versions: list[dict] = []
    history_file = paths.history / f"{note_slug(note_id)}.jsonl"
    if history_file.is_file():
        for line in history_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                versions.append(json.loads(line))
    current = paths.notes_cache / f"{note_slug(note_id)}.json"
    if current.is_file():
        versions.append(json.loads(current.read_text(encoding="utf-8")))
    return versions


def note_as_of(paths: TalamusPaths, title: str, timestamp: str) -> dict | None:
    """The note version current at the given time, or None.

    Accepts year / year-month / date / full datetime (robust parsing via
    ``temporal.parse_when``); raw ISO strings keep working as before."""
    from talamus.temporal import parse_when

    instant = parse_when(timestamp).instant_utc
    matching = [v for v in note_history(paths, title) if str(v.get("updated_at", "")) <= instant]
    return matching[-1] if matching else None
