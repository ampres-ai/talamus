"""LLM-as-judge verdicts + a deterministic refusal detector. Judges return a
normalized label; callers aggregate. Use an INDEPENDENT model (e.g. local
ollama) so the judge does not flatter the generator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_REFUSAL_MARKERS = (
    "non contiene", "non è possibile", "non e' possibile", "non sono in grado",
    "nessun contesto", "non ci sono informazioni", "non è sufficiente",
    "non disponibile", "i don't know", "i do not know", "cannot answer",
    "not enough", "no information", "non lo so",
)  # fmt: skip

_FAITHFUL_PROMPT = (
    "You are a strict fact-checker. Reply with ONE word.\n"
    "Given the CONTEXT and an ANSWER, reply GROUNDED if every factual claim in the "
    "answer is supported by the context, or HALLUCINATED if anything is not.\n\n"
    "CONTEXT:\n{context}\n\nANSWER:\n{answer}"
)

_CORRECT_PROMPT = (
    "You are grading an answer. Reply with ONE word: CORRECT, PARTIAL or WRONG.\n"
    "Given the QUESTION, a REFERENCE (known-correct info), and an ANSWER, judge "
    "whether the answer correctly answers the question per the reference.\n\n"
    "QUESTION: {question}\n\nREFERENCE:\n{reference}\n\nANSWER:\n{answer}"
)


def is_refusal(answer: str) -> bool:
    """Did the answer honestly decline? (good on out-of-scope questions)."""
    low = answer.lower()
    return any(marker in low for marker in _REFUSAL_MARKERS)


def faithfulness_verdict(answer: str, context: str, judge_llm) -> bool:
    """True = grounded (no hallucination)."""
    verdict = judge_llm.complete(_FAITHFUL_PROMPT.format(context=context[:6000], answer=answer))
    up = verdict.upper()
    return "GROUNDED" in up and "HALLUCINATED" not in up


def correctness_verdict(answer: str, question: str, reference: str, judge_llm) -> str:
    """Returns 'correct' | 'partial' | 'wrong'."""
    verdict = judge_llm.complete(
        _CORRECT_PROMPT.format(question=question, reference=reference[:4000], answer=answer)
    ).upper()
    if "CORRECT" in verdict:
        return "correct"
    if "PARTIAL" in verdict:
        return "partial"
    return "wrong"


class CachingJudge:
    """Wrap a judge LLM with a disk cache keyed by prompt hash, so re-runs
    during tuning are free. Verdicts are tiny strings."""

    def __init__(self, inner, cache_path: Path) -> None:
        self._inner = inner
        self._path = Path(cache_path)
        self._cache: dict[str, str] = {}
        if self._path.is_file():
            try:
                self._cache = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def complete(self, prompt: str) -> str:
        key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if key in self._cache:
            return self._cache[key]
        value = self._inner.complete(prompt)
        self._cache[key] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        return value


def agreement(primary: list[str], cross: list[str]) -> float:
    """Fraction of overlapping verdicts that match — the inter-judge confidence
    number reported alongside every judged result."""
    pairs = list(zip(primary, cross, strict=False))
    if not pairs:
        return 0.0
    return round(sum(1 for a, b in pairs if a == b) / len(pairs), 3)
