"""Persistent retrieval indexes — three channels, no embeddings (M4 + Fase RS).

The 2026-06 recall research measured the dominant failure class on real corpora:
cross-language vocabulary mismatch (Italian questions vs English-titled notes
and vice versa). The cure that won the ablations — without embeddings — is a
**character-trigram channel** over titles/aliases (cognates share trigrams:
architettur*ali*/architectur*e*, principi/principles) plus a lighter one over
summaries, blended with the stemmed lexical channel:

    score = lexical + 0.7 * trigram(title+aliases) + 0.3 * trigram(summary)

measured on the 120-case real eval-set: recall@5 +36%, MRR +40%, hit +31% over
the lexical-only baseline. Field weighting (title x3, aliases x2) is baked into
the lexical haystack. Backends: sqlite+FTS5 (preferred) with per-column queries,
or deterministic JSON posting lists. Indexes stay derived and rebuildable —
never source truth.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

from talamus.models import CanonicalNote
from talamus.paths import TalamusPaths
from talamus.textutil import tokens

_K1 = 1.5
_B = 0.75
W_TRI_TITLE = 0.7
W_TRI_SUMMARY = 0.3
_MAX_QUERY_TRIGRAMS = 64  # bound the OR-query cost
# Hub suppression (RS4): long "hub" notes accumulate blended score across many
# weak matches and crowd out short, precisely-titled notes. A mild length
# penalty divides by (avglen + LP·len)/avglen — it bites only where note lengths
# vary a lot (measured: docs cross-source +0.10, neutral on the uniform book).
_LENGTH_PENALTY = 0.5

_WORD = re.compile(r"[a-zà-ÿ0-9]+")


def sqlite_path(paths: TalamusPaths) -> Path:
    return paths.cache / "index.sqlite"


def postings_path(paths: TalamusPaths) -> Path:
    return paths.cache / "postings.json"


def _haystack(note: CanonicalNote) -> str:
    """Stemmed lexical field; title and aliases repeated = field weighting."""
    raw = " ".join(
        [
            *([note.title] * 3),
            *([" ".join(note.aliases)] * 2),
            " ".join(note.tags),
            note.retrieval_text,
            note.summary,
        ]
    )
    return " ".join(tokens(raw))


def trigram_tokens(text: str) -> str:
    """Character 3-grams as space-joined tokens — the IT<->EN cognate bridge."""
    grams: list[str] = []
    seen: set[str] = set()
    for word in _WORD.findall(text.lower()):
        if len(word) < 3:
            continue
        for i in range(len(word) - 2):
            gram = word[i : i + 3]
            if gram not in seen:
                seen.add(gram)
                grams.append(gram)
    return " ".join(grams)


def _tri_title(note: CanonicalNote) -> str:
    return trigram_tokens(f"{note.title} {' '.join(note.aliases)}")


def _tri_summary(note: CanonicalNote) -> str:
    return trigram_tokens(note.summary)


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
            "CREATE TABLE meta "
            "(note_id TEXT PRIMARY KEY, title TEXT, summary TEXT, aliases TEXT, hay_len INTEGER)"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE search USING "
            "fts5(note_id UNINDEXED, haystack, tri_title, tri_summary)"
        )
        for note in notes:
            haystack = _haystack(note)
            conn.execute(
                "INSERT INTO meta VALUES (?, ?, ?, ?, ?)",
                (
                    note.note_id,
                    note.title,
                    note.summary,
                    json.dumps(note.aliases),
                    len(haystack.split()),
                ),
            )
            conn.execute(
                "INSERT INTO search VALUES (?, ?, ?, ?)",
                (note.note_id, haystack, _tri_title(note), _tri_summary(note)),
            )
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp, target)


def _build_postings(paths: TalamusPaths, notes: list[CanonicalNote]) -> None:
    fields = {"haystack": _haystack, "tri_title": _tri_title, "tri_summary": _tri_summary}
    payload: dict = {"version": 2, "doc_count": len(notes), "meta": {}, "fields": {}}
    for field_name, extractor in fields.items():
        postings: dict[str, list[list]] = {}
        lengths: dict[str, int] = {}
        for note in notes:
            counts = Counter(extractor(note).split())
            lengths[note.note_id] = sum(counts.values())
            for term, tf in counts.items():
                postings.setdefault(term, []).append([note.note_id, tf])
        payload["fields"][field_name] = {
            "avgdl": (sum(lengths.values()) / len(lengths)) if lengths else 0.0,
            "lengths": lengths,
            "postings": postings,
        }
    for note in notes:
        payload["meta"][note.note_id] = {
            "title": note.title,
            "summary": note.summary,
            "aliases": note.aliases,
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


def _blend(channels: list[tuple[dict[str, float], float]]) -> dict[str, float]:
    """Normalize each channel to 0..1 and sum with its weight."""
    combined: dict[str, float] = {}
    for scores, weight in channels:
        top = max(scores.values(), default=0.0)
        if top <= 0:
            continue
        for note_id, score in scores.items():
            combined[note_id] = combined.get(note_id, 0.0) + weight * (score / top)
    return combined


def _apply_length_penalty(blended: dict[str, float], hay_len: dict[str, int]) -> dict[str, float]:
    """Damp hub notes by haystack length (RS4). avglen over the CANDIDATES so the
    penalty is relative, not absolute; missing lengths are left untouched."""
    if not _LENGTH_PENALTY or not hay_len:
        return blended
    lengths = [hay_len[n] for n in blended if n in hay_len]
    if not lengths:
        return blended
    avglen = sum(lengths) / len(lengths)
    if avglen <= 0:
        return blended
    out: dict[str, float] = {}
    for note_id, score in blended.items():
        length = hay_len.get(note_id)
        if length is None:
            out[note_id] = score
        else:
            out[note_id] = score * avglen / (avglen + _LENGTH_PENALTY * length)
    return out


def search_index(paths: TalamusPaths, query: str, limit: int = 5) -> list[dict]:
    """Query the persistent index (three blended channels).

    Returns [{note_id, title, summary, aliases, score}]."""
    if sqlite_path(paths).is_file():
        return _search_sqlite(paths, query, limit)
    if postings_path(paths).is_file():
        return _search_postings(paths, query, limit)
    return _search_legacy(paths, query, limit)


def _query_trigrams(query: str) -> list[str]:
    return trigram_tokens(query).split()[:_MAX_QUERY_TRIGRAMS]


def _search_sqlite(paths: TalamusPaths, query: str, limit: int) -> list[dict]:
    terms = list(dict.fromkeys(tokens(query)))
    grams = _query_trigrams(query)
    if not terms and not grams:
        return []
    conn = sqlite3.connect(sqlite_path(paths))
    pool = max(limit * 4, 20)

    def channel(column: str, words: list[str], weights: str) -> dict[str, float]:
        if not words:
            return {}
        match = f"{{{column}}}: " + " OR ".join(f'"{w}"' for w in words)
        try:
            rows = conn.execute(
                f"SELECT note_id, bm25(search, {weights}) AS rank FROM search "
                "WHERE search MATCH ? ORDER BY rank LIMIT ?",
                (match, pool),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        # FTS5 bm25() is smaller-is-better (negative): flip sign
        return {str(note_id): -float(rank) for note_id, rank in rows}

    try:
        blended = _blend(
            [
                (channel("haystack", terms, "0, 1.0, 0, 0"), 1.0),
                (channel("tri_title", grams, "0, 0, 1.0, 0"), W_TRI_TITLE),
                (channel("tri_summary", grams, "0, 0, 0, 1.0"), W_TRI_SUMMARY),
            ]
        )
        if not blended:
            return []
        hay_len = {
            str(nid): int(length)
            for nid, length in conn.execute("SELECT note_id, hay_len FROM meta").fetchall()
            if length is not None
        }
        blended = _apply_length_penalty(blended, hay_len)
        top = sorted(blended.items(), key=lambda item: (-item[1], item[0]))[:limit]
        results = []
        for note_id, score in top:
            row = conn.execute(
                "SELECT title, summary, aliases FROM meta WHERE note_id = ?", (note_id,)
            ).fetchone()
            if row is None:
                continue
            results.append(
                {
                    "note_id": note_id,
                    "title": row[0],
                    "summary": row[1],
                    "aliases": json.loads(row[2] or "[]"),
                    "score": round(score, 4),
                }
            )
        return results
    finally:
        conn.close()


def _field_bm25(field: dict, words: list[str]) -> dict[str, float]:
    lengths = field.get("lengths", {})
    postings = field.get("postings", {})
    doc_count = max(len(lengths), 1)
    avgdl = float(field.get("avgdl", 0.0)) or 1.0
    scores: dict[str, float] = {}
    for word in words:
        plist = postings.get(word, [])
        df = len(plist)
        if not df:
            continue
        idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
        for note_id, tf in plist:
            doc_len = int(lengths.get(note_id, 0)) or 1
            denom = tf + _K1 * (1 - _B + _B * doc_len / avgdl)
            scores[note_id] = scores.get(note_id, 0.0) + idf * (tf * (_K1 + 1)) / denom
    return scores


def _search_postings(paths: TalamusPaths, query: str, limit: int) -> list[dict]:
    try:
        data = json.loads(postings_path(paths).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    fields = data.get("fields", {})
    meta = data.get("meta", {})
    terms = list(dict.fromkeys(tokens(query)))
    grams = _query_trigrams(query)
    blended = _blend(
        [
            (_field_bm25(fields.get("haystack", {}), terms), 1.0),
            (_field_bm25(fields.get("tri_title", {}), grams), W_TRI_TITLE),
            (_field_bm25(fields.get("tri_summary", {}), grams), W_TRI_SUMMARY),
        ]
    )
    hay_lengths = fields.get("haystack", {}).get("lengths", {})
    blended = _apply_length_penalty(blended, {nid: int(v) for nid, v in hay_lengths.items()})
    ranked = sorted(blended.items(), key=lambda item: (-item[1], item[0]))[:limit]
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
    from talamus.naming import note_slug
    from talamus.search import BM25Index
    from talamus.store import load_notes

    if not paths.index_file.is_file():
        return []
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
