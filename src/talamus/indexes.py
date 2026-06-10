"""Persistent retrieval indexes — kill the O(N) scans (PRD 9.4 / F3 / M4).

The M0 baseline measured the truth: at 10.000 notes a single ``search_notes``
cost ~8.5s, because every query re-read all note JSONs and scanned every BM25
document. This module replaces that with indexes persisted at build time:

- **sqlite + FTS5** (stdlib) when available: terms, metadata (title/aliases/
  summary) and BM25 ranking inside the database — queries touch only matching
  rows.
- **JSON posting lists** as the deterministic fallback: per-term postings with
  tf/df/lengths, so a query reads only the postings of its own terms.

Tokens are stemmed with the same ``textutil.tokens`` used everywhere, so both
backends rank consistently with the legacy index. The indexes are derived and
rebuildable — never source truth.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from collections import Counter
from pathlib import Path

from talamus.models import CanonicalNote
from talamus.paths import TalamusPaths
from talamus.textutil import tokens

_K1 = 1.5
_B = 0.75


def sqlite_path(paths: TalamusPaths) -> Path:
    return paths.cache / "index.sqlite"


def postings_path(paths: TalamusPaths) -> Path:
    return paths.cache / "postings.json"


def _haystack(note: CanonicalNote) -> str:
    raw = " ".join(
        [note.title, " ".join(note.aliases), " ".join(note.tags), note.retrieval_text, note.summary]
    )
    return " ".join(tokens(raw))


def _fts5_available() -> bool:
    try:
        with sqlite3.connect(":memory:") as conn:
            conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False


def build_search_index(paths: TalamusPaths, notes: list[CanonicalNote]) -> str:
    """(Re)build the persistent index from canonical notes. Returns the backend name."""
    paths.cache.mkdir(parents=True, exist_ok=True)
    if _fts5_available():
        _build_sqlite(paths, notes)
        postings_path(paths).unlink(missing_ok=True)
        return "sqlite-fts5"
    _build_postings(paths, notes)
    sqlite_path(paths).unlink(missing_ok=True)
    return "json-postings"


def _build_sqlite(paths: TalamusPaths, notes: list[CanonicalNote]) -> None:
    target = sqlite_path(paths)
    tmp = target.with_suffix(".sqlite.tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        conn.execute(
            "CREATE TABLE meta (note_id TEXT PRIMARY KEY, title TEXT, summary TEXT, aliases TEXT)"
        )
        conn.execute("CREATE VIRTUAL TABLE search USING fts5(note_id UNINDEXED, haystack)")
        for note in notes:
            conn.execute(
                "INSERT INTO meta VALUES (?, ?, ?, ?)",
                (note.note_id, note.title, note.summary, json.dumps(note.aliases)),
            )
            conn.execute(
                "INSERT INTO search VALUES (?, ?)",
                (note.note_id, _haystack(note)),
            )
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp, target)


def _build_postings(paths: TalamusPaths, notes: list[CanonicalNote]) -> None:
    postings: dict[str, list[list]] = {}
    lengths: dict[str, int] = {}
    meta: dict[str, dict] = {}
    for note in notes:
        counts = Counter(_haystack(note).split())
        lengths[note.note_id] = sum(counts.values())
        meta[note.note_id] = {
            "title": note.title,
            "summary": note.summary,
            "aliases": note.aliases,
        }
        for term, tf in counts.items():
            postings.setdefault(term, []).append([note.note_id, tf])
    payload = {
        "version": 1,
        "doc_count": len(notes),
        "avgdl": (sum(lengths.values()) / len(lengths)) if lengths else 0.0,
        "lengths": lengths,
        "postings": postings,
        "meta": meta,
    }
    target = postings_path(paths)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def backend_info(paths: TalamusPaths) -> dict:
    if sqlite_path(paths).is_file():
        return {"backend": "sqlite-fts5", "bytes": sqlite_path(paths).stat().st_size}
    if postings_path(paths).is_file():
        return {"backend": "json-postings", "bytes": postings_path(paths).stat().st_size}
    if paths.index_file.is_file():
        return {"backend": "legacy-bm25", "bytes": paths.index_file.stat().st_size}
    return {"backend": "none", "bytes": 0}


def search_index(paths: TalamusPaths, query: str, limit: int = 5) -> list[dict]:
    """Query the persistent index. Returns [{note_id, title, summary, aliases, score}]."""
    if sqlite_path(paths).is_file():
        return _search_sqlite(paths, query, limit)
    if postings_path(paths).is_file():
        return _search_postings(paths, query, limit)
    return _search_legacy(paths, query, limit)


def _search_sqlite(paths: TalamusPaths, query: str, limit: int) -> list[dict]:
    terms = tokens(query)
    if not terms:
        return []
    match = " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))
    conn = sqlite3.connect(sqlite_path(paths))
    try:
        rows = conn.execute(
            "SELECT s.note_id, m.title, m.summary, m.aliases, bm25(search) AS rank "
            "FROM search s JOIN meta m ON m.note_id = s.note_id "
            "WHERE search MATCH ? ORDER BY rank LIMIT ?",
            (match, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [
        {
            "note_id": note_id,
            "title": title,
            "summary": summary,
            "aliases": json.loads(aliases or "[]"),
            # FTS5 bm25() is "smaller is better" (negative); flip to positive
            "score": round(-float(rank), 4),
        }
        for note_id, title, summary, aliases, rank in rows
    ]


def _search_postings(paths: TalamusPaths, query: str, limit: int) -> list[dict]:
    try:
        data = json.loads(postings_path(paths).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    doc_count = int(data.get("doc_count", 0)) or 1
    avgdl = float(data.get("avgdl", 0.0)) or 1.0
    lengths = data.get("lengths", {})
    postings = data.get("postings", {})
    meta = data.get("meta", {})
    scores: dict[str, float] = {}
    for term in dict.fromkeys(tokens(query)):
        plist = postings.get(term, [])
        df = len(plist)
        if not df:
            continue
        idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
        for note_id, tf in plist:
            doc_len = int(lengths.get(note_id, 0)) or 1
            denom = tf + _K1 * (1 - _B + _B * doc_len / avgdl)
            scores[note_id] = scores.get(note_id, 0.0) + idf * (tf * (_K1 + 1)) / denom
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [
        {
            "note_id": note_id,
            "title": meta.get(note_id, {}).get("title", note_id),
            "summary": meta.get(note_id, {}).get("summary", ""),
            "aliases": meta.get(note_id, {}).get("aliases", []),
            "score": round(score, 4),
        }
        for note_id, score in ranked
    ]


def _search_legacy(paths: TalamusPaths, query: str, limit: int) -> list[dict]:
    """Compatibility path for brains indexed before M4 (bm25.json + note JSONs)."""
    from talamus.search import BM25Index
    from talamus.store import load_notes

    if not paths.index_file.is_file():
        return []
    from talamus.naming import note_slug

    index = BM25Index.load(paths.index_file)
    by_slug = {note_slug(note.title): note for note in load_notes(paths)}
    results = []
    for hit in index.search(query, limit=limit):
        found = by_slug.get(str(hit["id"]))
        if found is None:
            continue
        results.append(
            {
                "note_id": found.note_id,
                "title": found.title,
                "summary": found.summary,
                "aliases": found.aliases,
                "score": round(float(hit["score"]), 4),
            }
        )
    return results
