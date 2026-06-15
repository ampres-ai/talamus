"""Ranking metrics scored against qrels. relevant = set of relevant doc_ids;
grades = {doc_id: relevance_grade} for graded (nDCG) metrics."""

from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    found = sum(1 for doc_id in retrieved[:k] if doc_id in relevant)
    return found / len(relevant)


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def hit_rate(retrieved: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if any(doc_id in relevant for doc_id in retrieved[:k]) else 0.0


def _dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(retrieved: list[str], grades: dict[str, int], k: int) -> float:
    if not grades:
        return 0.0
    gains = [float(grades.get(doc_id, 0)) for doc_id in retrieved[:k]]
    ideal = sorted((float(g) for g in grades.values()), reverse=True)[:k]
    idcg = _dcg(ideal)
    return _dcg(gains) / idcg if idcg > 0 else 0.0
