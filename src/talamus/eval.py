"""Retrieval evaluation harness — measure recall@k/precision@k/MRR, don't guess.

A *case* is a question plus the note titles that SHOULD be retrieved. A *retriever*
maps (question, k) to a ranked list of note titles. The harness runs every case
through a retriever and reports deterministic metrics, so a change to retrieval
(reranking, budgets, graph-routing) can be judged by numbers, not vibes.

Cases carry an optional ``category`` (direct, vague, cross-source, temporal, code,
negative, ...). A case with an empty ``relevant`` list is a *negative* case: the
brain holds nothing pertinent, and at the retrieval level success means returning
no candidates. Aggregate metrics are computed over answerable cases only;
negatives get their own rejection rate.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from talamus.paths import TalamusPaths
from talamus.recall import search_notes

# (question, k) -> ranked note titles, best first.
Retriever = Callable[[str, int], list[str]]

NEGATIVE_CATEGORY = "negative"


def _norm(title: str) -> str:
    return title.strip().lower()


@dataclass(frozen=True)
class EvalCase:
    question: str
    relevant: list[str]  # note titles a good retriever must surface; empty = negative case
    category: str = ""
    case_id: str = ""

    @property
    def negative(self) -> bool:
        return not self.relevant


@dataclass(frozen=True)
class CaseResult:
    question: str
    retrieved: list[str]
    relevant: list[str]
    hit: bool
    recall: float
    precision: float
    reciprocal_rank: float
    category: str = ""
    case_id: str = ""
    negative: bool = False
    negative_pass: bool = False

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "question": self.question,
            "category": self.category,
            "retrieved": self.retrieved,
            "relevant": self.relevant,
            "hit": self.hit,
            "recall": round(self.recall, 4),
            "precision": round(self.precision, 4),
            "reciprocal_rank": round(self.reciprocal_rank, 4),
            "negative": self.negative,
            "negative_pass": self.negative_pass,
        }


@dataclass(frozen=True)
class EvalReport:
    k: int
    n_cases: int
    recall_at_k: float
    precision_at_k: float
    mrr: float
    hit_rate: float
    cases: list[CaseResult]
    n_negative: int = 0
    negative_rejection: float = 0.0
    categories: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "k": self.k,
            "n_cases": self.n_cases,
            "recall_at_k": round(self.recall_at_k, 4),
            "precision_at_k": round(self.precision_at_k, 4),
            "mrr": round(self.mrr, 4),
            "hit_rate": round(self.hit_rate, 4),
            "n_negative": self.n_negative,
            "negative_rejection": round(self.negative_rejection, 4),
            "categories": self.categories,
            "cases": [c.to_dict() for c in self.cases],
        }

    def format_table(self) -> str:
        answerable = self.n_cases - self.n_negative
        lines = [
            f"Retrieval evaluation — {self.n_cases} cases ({answerable} answerable), k={self.k}",
            f"  recall@{self.k}    {self.recall_at_k:.3f}",
            f"  precision@{self.k} {self.precision_at_k:.3f}",
            f"  MRR          {self.mrr:.3f}",
            f"  hit-rate     {self.hit_rate:.3f}",
        ]
        if self.n_negative:
            lines.append(
                f"  negatives    {self.n_negative} cases, rejection {self.negative_rejection:.3f}"
            )
        for name in sorted(self.categories):
            stats = self.categories[name]
            lines.append(
                f"  [{name}] n={stats['n']}"
                f" recall {stats['recall_at_k']:.3f}"
                f" MRR {stats['mrr']:.3f}"
                f" hit {stats['hit_rate']:.3f}"
            )
        misses = [c for c in self.cases if not c.negative and not c.hit]
        if misses:
            lines.append(f"  missed ({len(misses)}):")
            lines.extend(f"    - {c.question}" for c in misses)
        return "\n".join(lines)


def evaluate_case(case: EvalCase, retriever: Retriever, k: int) -> CaseResult:
    retrieved = retriever(case.question, k)[:k]
    if case.negative:
        return CaseResult(
            question=case.question,
            retrieved=retrieved,
            relevant=[],
            hit=False,
            recall=0.0,
            precision=0.0,
            reciprocal_rank=0.0,
            category=case.category,
            case_id=case.case_id,
            negative=True,
            negative_pass=not retrieved,
        )
    retrieved_norm = [_norm(t) for t in retrieved]
    relevant_norm = {_norm(t) for t in case.relevant}
    matched = relevant_norm.intersection(retrieved_norm)
    recall = len(matched) / len(relevant_norm) if relevant_norm else 0.0
    precision = len(matched) / len(retrieved) if retrieved else 0.0
    rr = 0.0
    for rank, title in enumerate(retrieved_norm, start=1):
        if title in relevant_norm:
            rr = 1.0 / rank
            break
    return CaseResult(
        question=case.question,
        retrieved=retrieved,
        relevant=case.relevant,
        hit=bool(matched),
        recall=recall,
        precision=precision,
        reciprocal_rank=rr,
        category=case.category,
        case_id=case.case_id,
    )


def _aggregate(results: list[CaseResult], k: int) -> dict:
    n = len(results) or 1
    return {
        "n": len(results),
        "recall_at_k": round(sum(r.recall for r in results) / n, 4),
        "precision_at_k": round(sum(r.precision for r in results) / n, 4),
        "mrr": round(sum(r.reciprocal_rank for r in results) / n, 4),
        "hit_rate": round(sum(1 for r in results if r.hit) / n, 4),
    }


def evaluate(cases: list[EvalCase], retriever: Retriever, k: int = 5) -> EvalReport:
    results = [evaluate_case(case, retriever, k) for case in cases]
    answerable = [r for r in results if not r.negative]
    negatives = [r for r in results if r.negative]
    n = len(answerable) or 1
    categories: dict[str, dict] = {}
    for name in sorted({r.category for r in answerable if r.category}):
        categories[name] = _aggregate([r for r in answerable if r.category == name], k)
    return EvalReport(
        k=k,
        n_cases=len(results),
        recall_at_k=sum(r.recall for r in answerable) / n,
        precision_at_k=sum(r.precision for r in answerable) / n,
        mrr=sum(r.reciprocal_rank for r in answerable) / n,
        hit_rate=sum(1 for r in answerable if r.hit) / n,
        cases=results,
        n_negative=len(negatives),
        negative_rejection=(
            sum(1 for r in negatives if r.negative_pass) / len(negatives) if negatives else 0.0
        ),
        categories=categories,
    )


def search_retriever(paths: TalamusPaths) -> Retriever:
    """The production retriever (`search_notes`) wrapped as a title-ranking function."""
    return lambda question, k: [r["title"] for r in search_notes(paths, question, limit=k)]


def load_cases(path: Path, category: str | None = None) -> list[EvalCase]:
    """Read cases from JSON: a list of {"question", "relevant": [...]} or {"cases": [...]}.

    Entries may carry "category" and "id". An entry whose category is "negative" may
    have an empty "relevant" list (no pertinent notes exist); any other entry without
    relevant titles is skipped as malformed. Pass ``category`` to filter.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data["cases"] if isinstance(data, dict) else data
    cases: list[EvalCase] = []
    for entry in raw:
        question = str(entry.get("question", "")).strip()
        relevant = [str(t) for t in entry.get("relevant", [])]
        entry_category = str(entry.get("category", "")).strip()
        if not question:
            continue
        if not relevant and entry_category != NEGATIVE_CATEGORY:
            continue
        if category is not None and entry_category != category:
            continue
        cases.append(
            EvalCase(
                question=question,
                relevant=relevant,
                category=entry_category,
                case_id=str(entry.get("id", "")),
            )
        )
    return cases
