from __future__ import annotations

import re

from benchmarks.shootout.systems.base import Doc, IngestStats

_WORD = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class BM25System:
    """Vanilla BM25 (rank-bm25), the lexical baseline. Same lowercase
    word-tokenization for docs and queries."""

    name = "bm25"

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._bm25 = None

    def ingest(self, docs: list[Doc]) -> IngestStats:
        from rank_bm25 import BM25Okapi

        self._ids = [doc.doc_id for doc in docs]
        tokenized = [_tokenize(f"{doc.title} {doc.text}") for doc in docs]
        self._bm25 = BM25Okapi(tokenized)
        return IngestStats(index_bytes=sum(len(t) for toks in tokenized for t in toks))

    def query(self, q: str, k: int) -> list[str]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(q))
        ranked = sorted(zip(scores, self._ids, strict=True), key=lambda s: (-s[0], s[1]))
        return [doc_id for score, doc_id in ranked[:k] if score > 0]
