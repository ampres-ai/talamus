"""LLM-wiki competitor: at ingest, the LLM writes a wiki-style augmentation per
doc (the viral repo's mechanism), then retrieval runs over the augmented text.
Pointed at the user's local/subscription engine (€0), not a hosted API. This is
a faithful minimal stand-in for the upstream package (which is hosted-API-locked),
labelled as such in the report."""

from __future__ import annotations

import time

from benchmarks.shootout.systems.base import Doc, IngestStats

_AUG_PROMPT = (
    "Write 10 keywords and aliases (comma-separated) that someone might use to "
    "look up the following note. Output only the keywords.\n\nNOTE:\n{text}"
)


class LLMWikiSystem:
    name = "llm-wiki"

    def __init__(self, llm) -> None:
        self._llm = llm
        self._docs: dict[str, str] = {}
        self._calls = 0

    def ingest(self, docs: list[Doc]) -> IngestStats:
        start = time.perf_counter()
        for doc in docs:
            try:
                aug = self._llm.complete(_AUG_PROMPT.format(text=f"{doc.title}. {doc.text}"))
            except Exception:
                aug = ""
            self._calls += 1
            self._docs[doc.doc_id] = f"{doc.title} {doc.text} {aug}".lower()
        return IngestStats(seconds=time.perf_counter() - start, llm_calls=self._calls)

    def query(self, q: str, k: int) -> list[str]:
        words = [w for w in q.lower().split() if w]
        scored = [
            (doc_id, sum(text.count(w) for w in words)) for doc_id, text in self._docs.items()
        ]
        scored = [(d, s) for d, s in scored if s > 0]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [d for d, _ in scored[:k]]
