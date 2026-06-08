from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path


def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower())


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: dict[str, Counter[str]] = {}
        self._lengths: dict[str, int] = {}
        self._df: Counter[str] = Counter()

    def add(self, doc_id: str, text: str) -> None:
        counts = Counter(_terms(text))
        self._docs[doc_id] = counts
        self._lengths[doc_id] = sum(counts.values())
        for term in counts:
            self._df[term] += 1

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if not self._docs:
            return []
        q_terms = _terms(query)
        avgdl = sum(self._lengths.values()) / len(self._lengths)
        results: list[dict] = []
        total_docs = len(self._docs)
        for doc_id, counts in self._docs.items():
            score = 0.0
            doc_len = self._lengths[doc_id]
            for term in q_terms:
                tf = counts.get(term, 0)
                if tf == 0:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
                denom = tf + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
                score += idf * (tf * (self.k1 + 1)) / denom
            if score > 0:
                results.append({"id": doc_id, "score": score})
        return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]

    def to_dict(self) -> dict:
        return {
            "k1": self.k1,
            "b": self.b,
            "docs": {doc_id: dict(counts) for doc_id, counts in self._docs.items()},
            "lengths": self._lengths,
            "df": dict(self._df),
        }

    @classmethod
    def from_dict(cls, data: dict) -> BM25Index:
        index = cls(k1=float(data["k1"]), b=float(data["b"]))
        index._docs = {doc_id: Counter(counts) for doc_id, counts in data["docs"].items()}
        index._lengths = {doc_id: int(length) for doc_id, length in data["lengths"].items()}
        index._df = Counter(data["df"])
        return index

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> BM25Index:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
