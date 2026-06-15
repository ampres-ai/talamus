"""Run every system over the same judged corpus and aggregate the metrics.
Apples-to-apples by construction: same docs, queries and qrels for all."""

from __future__ import annotations

import time
from dataclasses import asdict

from benchmarks.shootout.corpora.judged import JudgedCorpus
from benchmarks.shootout.metrics import hit_rate, mrr, ndcg_at_k, recall_at_k
from benchmarks.shootout.systems.base import RetrievalSystem

__all__ = ["JudgedCorpus", "run_shootout"]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_shootout(systems: list[RetrievalSystem], corpus: JudgedCorpus, k: int = 10) -> dict:
    docs = corpus.as_docs()
    out: dict = {"k": k, "n_docs": len(docs), "n_queries": len(corpus.queries), "systems": {}}
    for system in systems:
        ingest = system.ingest(docs)
        cases: list[dict] = []
        latencies: list[float] = []
        for query_id, text in corpus.queries.items():
            relevant = set(corpus.qrels.get(query_id, {}))
            start = time.perf_counter()
            retrieved = system.query(text, k)
            latencies.append((time.perf_counter() - start) * 1000)
            cases.append(
                {
                    "query_id": query_id,
                    "recall_at_k": recall_at_k(retrieved, relevant, k),
                    "mrr": mrr(retrieved, relevant),
                    "hit": hit_rate(retrieved, relevant, k),
                    "ndcg_at_k": ndcg_at_k(retrieved, corpus.qrels.get(query_id, {}), k),
                }
            )
        out["systems"][system.name] = {
            "n_queries": len(cases),
            "recall_at_k": _mean([c["recall_at_k"] for c in cases]),
            "mrr": _mean([c["mrr"] for c in cases]),
            "hit_rate": _mean([c["hit"] for c in cases]),
            "ndcg_at_k": _mean([c["ndcg_at_k"] for c in cases]),
            "latency_ms_p50": sorted(latencies)[len(latencies) // 2] if latencies else 0.0,
            "ingest": asdict(ingest),
            "cases": cases,
        }
    return out
