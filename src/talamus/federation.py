"""Local federated read-index across registered brains.

The central brain can search *all* registered, federated, non-sensitive brains.
The index stores searchable metadata and **pointers** (`brain_id + note_id +
note_path`) — never source truth: every answer path must read the real note from
the owning brain. Rebuildable at any time from the registered brains without
modifying them.

V1 backend: deterministic JSON rows + the built-in BM25 index, stored under
``<TALAMUS_HOME>/federation/``. The sqlite/FTS5 backend arrives with the
persistent-index milestone (M4) behind the same functions.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from talamus.domains import load_overview
from talamus.naming import note_filename
from talamus.paths import TalamusPaths
from talamus.registry import BrainInfo, load_registry, talamus_home
from talamus.search import BM25Index
from talamus.store import load_notes

_BOOST = 1.25  # proximity boost for the current and central brains (F1.11)


def federation_dir(home: Path | None = None) -> Path:
    return (home or talamus_home()) / "federation"


def _rows_path(home: Path | None = None) -> Path:
    return federation_dir(home) / "index.json"


def _bm25_path(home: Path | None = None) -> Path:
    return federation_dir(home) / "bm25.json"


def _row_id(brain_id: str, note_id: str) -> str:
    return f"{brain_id}::{note_id}"


def _brain_rows(brain: BrainInfo) -> list[dict]:
    paths = TalamusPaths(brain.root())
    domains_by_title: dict[str, list[str]] = {}
    for domain in load_overview(paths):
        for member in domain.get("members", []):
            domains_by_title.setdefault(str(member), []).append(str(domain.get("name", "")))
    rows: list[dict] = []
    for note in load_notes(paths):
        rows.append(
            {
                "brain_id": brain.id,
                "brain_name": brain.name,
                "brain_type": brain.type,
                "sensitive": brain.sensitive,
                "note_id": note.note_id,
                "note_path": str(paths.notes / note_filename(note.title)),
                "title": note.title,
                "aliases": note.aliases,
                "summary": note.summary,
                "retrieval_text": note.retrieval_text,
                "tags": note.tags,
                "domains": domains_by_title.get(note.title, []),
                "relations": [{"type": r.relation, "target": r.target} for r in note.relations],
                "updated_at": note.updated_at,
                "source_refs_count": len(note.sources),
                "fresh": True,
            }
        )
    return rows


def build_federated_index(home: Path | None = None) -> dict:
    """(Re)build the federated index from every registered, federated brain.

    Brains that are missing or unreadable degrade to warnings — they never fail
    the build (F1.10). Source brains are read-only here.
    """
    registry = load_registry(home)
    rows: list[dict] = []
    brains_report: list[dict] = []
    warnings: list[str] = []
    for brain in registry.brains:
        if not brain.federated:
            brains_report.append({"brain": brain.name, "notes": 0, "skipped": "not federated"})
            continue
        root = brain.root()
        if not (root / "talamus.json").exists():
            warnings.append(f"brain '{brain.name}' missing or uninitialized at {root}")
            brains_report.append({"brain": brain.name, "notes": 0, "skipped": "missing"})
            continue
        try:
            brain_rows = _brain_rows(brain)
        except Exception as exc:
            warnings.append(f"brain '{brain.name}' unreadable: {exc}")
            brains_report.append({"brain": brain.name, "notes": 0, "skipped": "unreadable"})
            continue
        rows.extend(brain_rows)
        brains_report.append({"brain": brain.name, "notes": len(brain_rows)})
    index = BM25Index()
    for row in rows:
        haystack = " ".join(
            [
                row["title"],
                " ".join(row["aliases"]),
                " ".join(row["tags"]),
                " ".join(row["domains"]),
                row["summary"],
                row["retrieval_text"],
            ]
        )
        index.add(_row_id(row["brain_id"], row["note_id"]), haystack)
    out_dir = federation_dir(home)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rows": rows}
    _rows_path(home).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    index.save(_bm25_path(home))
    return {
        "built_at": payload["built_at"],
        "rows": len(rows),
        "brains": brains_report,
        "warnings": warnings,
    }


def federation_status(home: Path | None = None) -> dict:
    path = _rows_path(home)
    if not path.is_file():
        return {"built": False, "rows": 0, "built_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"built": False, "rows": 0, "built_at": None, "error": "corrupt index"}
    per_brain: dict[str, int] = {}
    for row in data.get("rows", []):
        per_brain[row["brain_name"]] = per_brain.get(row["brain_name"], 0) + 1
    return {
        "built": True,
        "built_at": data.get("built_at"),
        "rows": len(data.get("rows", [])),
        "per_brain": per_brain,
    }


def search_federated(
    query: str,
    limit: int = 8,
    home: Path | None = None,
    include_sensitive: bool = False,
    boost_brain_ids: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    """Query the federated index. Returns (pointer rows with scores, warnings)."""
    warnings: list[str] = []
    rows_file = _rows_path(home)
    bm25_file = _bm25_path(home)
    if not rows_file.is_file() or not bm25_file.is_file():
        warnings.append("federated index not built; run `talamus brains index --rebuild`")
        return [], warnings
    try:
        data = json.loads(rows_file.read_text(encoding="utf-8"))
        index = BM25Index.load(bm25_file)
    except (json.JSONDecodeError, OSError) as exc:
        warnings.append(f"federated index unreadable: {exc}")
        return [], warnings
    by_id = {_row_id(r["brain_id"], r["note_id"]): r for r in data.get("rows", [])}
    boosts = set(boost_brain_ids or [])
    scored: list[tuple[float, dict]] = []
    for hit in index.search(query, limit=max(limit * 3, limit)):
        row = by_id.get(str(hit["id"]))
        if row is None:
            continue
        if row.get("sensitive") and not include_sensitive:
            continue
        score = float(hit["score"])
        if row["brain_id"] in boosts:
            score *= _BOOST
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = [{**row, "score": round(score, 4)} for score, row in scored[:limit]]
    return results, warnings
