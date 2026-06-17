"""Agent-memory benchmark: store insights, then recall the right one across a
fresh session. This is mem0's actual design point (conversational memory), so
comparing it here is fair — not forced onto document IR. A `MemorySystem`
exposes remember(text, key) + recall(query, k); Talamus's recall/remember (SDK)
is the peer to mem0."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentMemCase:
    query: str
    want_key: str


def score_recall(system, cases: list[AgentMemCase], k: int = 5) -> dict:
    """Fraction of cases where the wanted insight is recalled in the top k."""
    hits = 0
    for case in cases:
        keys = system.recall(case.query, k)
        if case.want_key in keys:
            hits += 1
    n = len(cases)
    return {"n": n, "hit_rate": round(hits / n, 3) if n else 0.0}
