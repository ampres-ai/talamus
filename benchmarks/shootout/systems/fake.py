from __future__ import annotations

import re

from benchmarks.shootout.systems.base import Doc, IngestStats

_WORD = re.compile(r"[a-z0-9]+")


class FakeSystem:
    """Deterministic word-overlap retriever — for testing the harness with zero
    deps and zero LLM. Not a real competitor; ranks by query-word coverage."""

    name = "fake"

    def __init__(self) -> None:
        self._docs: dict[str, set[str]] = {}

    def ingest(self, docs: list[Doc]) -> IngestStats:
        for doc in docs:
            self._docs[doc.doc_id] = set(_WORD.findall(f"{doc.title} {doc.text}".lower()))
        return IngestStats(index_bytes=sum(len(w) for ws in self._docs.values() for w in ws))

    def query(self, q: str, k: int) -> list[str]:
        terms = set(_WORD.findall(q.lower()))
        scored = [
            (-len(terms & words), doc_id) for doc_id, words in self._docs.items() if terms & words
        ]
        scored.sort()
        return [doc_id for _, doc_id in scored[:k]]
