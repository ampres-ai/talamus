"""Watch mode: drop a file into the watched folder and it becomes notes.

Consent moves from per-run to per-folder: STARTING the watch is the consent.
Guard rails keep it honest anyway — a daily cap bounds the LLM spend, big
multi-chunk documents are skipped with a notice (they keep the estimate +
`--yes` contract of `talamus ingest`), unchanged files are hash-skipped, and
everything the watch does is printed as it happens. Pure stdlib polling: no
watchdog dependency, works on every OS."""

from __future__ import annotations

import json
import time
from pathlib import Path

from talamus.errors import EngineFailed, EngineNotFound, TalamusError
from talamus.ingest import _SUPPORTED, _content_hash, _load_hashes, estimate_chunks, ingest_file
from talamus.paths import TalamusPaths
from talamus.routing import Router
from talamus.sources import extract_text

DEFAULT_INTERVAL = 5.0
DEFAULT_DAILY_CAP = 50  # ingested files per day: bounds the spend the watch can cause


def _cap_path(paths: TalamusPaths) -> Path:
    return paths.talamus_dir / "watch-cap.json"


def _cap_used(paths: TalamusPaths) -> int:
    path = _cap_path(paths)
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if data.get("date") != time.strftime("%Y-%m-%d"):
        return 0
    return int(data.get("used", 0))


def _cap_record(paths: TalamusPaths, used: int) -> None:
    _cap_path(paths).write_text(
        json.dumps({"date": time.strftime("%Y-%m-%d"), "used": used}), encoding="utf-8"
    )


def _watchable(paths: TalamusPaths, path: Path) -> bool:
    """Supported source files only — never the brain's own output (notes/,
    .talamus/) or hidden directories, which would loop the watch on itself."""
    if not path.is_file() or path.suffix.lower() not in _SUPPORTED:
        return False
    try:
        relative = path.resolve().relative_to(paths.project_root.resolve())
    except ValueError:
        relative = path
    parts = relative.parts
    if any(part.startswith(".") for part in parts):
        return False
    return "notes" != (parts[0] if parts else "")


def scan_once(
    paths: TalamusPaths,
    directory: Path,
    router: Router,
    daily_cap: int = DEFAULT_DAILY_CAP,
) -> dict:
    """One pass over the watched folder. Returns what happened:
    {ingested, skipped_large, capped, failed} — file names, not paths."""
    ingested: list[str] = []
    skipped_large: list[str] = []
    failed: list[str] = []
    capped = 0
    hashes = _load_hashes(paths)
    used = _cap_used(paths)
    for path in sorted(directory.rglob("*")):
        if not _watchable(paths, path):
            continue
        try:
            text = extract_text(path)
        except TalamusError:
            continue
        if hashes.get(path.name) == _content_hash(text):
            continue
        if estimate_chunks(paths, path)["chunks"] > 1:
            skipped_large.append(path.name)
            continue
        if used >= daily_cap:
            capped += 1
            continue
        try:
            ingest_file(paths, path, router)
        except (EngineFailed, EngineNotFound):
            failed.append(path.name)
            continue
        used += 1
        _cap_record(paths, used)
        ingested.append(path.name)
    return {
        "ingested": ingested,
        "skipped_large": skipped_large,
        "capped": capped,
        "failed": failed,
    }


def watch_folder(
    paths: TalamusPaths,
    directory: Path,
    router: Router,
    interval: float = DEFAULT_INTERVAL,
    daily_cap: int = DEFAULT_DAILY_CAP,
    once: bool = False,
) -> dict:
    """Poll the folder until interrupted (Ctrl+C); ``once`` runs a single pass.
    Returns the last pass's result."""
    result: dict = {}
    while True:
        result = scan_once(paths, directory, router, daily_cap=daily_cap)
        for name in result["ingested"]:
            print(f"watch: ingested {name}")
        for name in result["skipped_large"]:
            print(f"watch: skipped {name} (multi-chunk — run: talamus ingest {name!r} --yes)")
        for name in result["failed"]:
            print(f"watch: engine failed on {name} — will retry next pass")
        if result["capped"]:
            print(f"watch: daily cap reached ({daily_cap}) — {result['capped']} file(s) waiting")
        if once:
            return result
        time.sleep(interval)
