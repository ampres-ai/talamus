"""Layer-2 workflow profiler: the axes a SciFact-style recall benchmark cannot
see — token efficiency, verifiability, cost-per-answer, hallucination rate.
These are where Talamus's moats live and where competitors score ✗.

Deterministic functions run free in CI; the LLM-judge one (hallucination rate)
needs a judge model (e.g. local ollama) and is exercised on demand."""

from __future__ import annotations

from talamus.budget import estimate_tokens
from talamus.correct import provenance_status
from talamus.paths import TalamusPaths
from talamus.store import load_notes


def token_efficiency(paths: TalamusPaths) -> dict:
    """Targeted recall vs loading the whole brain — the core efficiency claim.
    Tokens via talamus.budget.estimate_tokens (no external tokenizer)."""
    from talamus.recall import recall_context, search_notes

    notes = load_notes(paths)
    md_files = sorted(paths.notes.glob("*.md"))
    if not notes or not md_files:
        return {"notes": 0}
    load_all = estimate_tokens("\n\n".join(p.read_text(encoding="utf-8") for p in md_files))
    questions = [n.title for n in notes][:12]
    recall = [estimate_tokens(recall_context(paths, q)) for q in questions]
    search = [
        estimate_tokens(
            "\n".join(f"- {r['title']}: {r['summary']}" for r in search_notes(paths, q))
        )
        for q in questions
    ]
    avg_recall = sum(recall) / len(recall)
    avg_search = sum(search) / len(search)
    return {
        "notes": len(notes),
        "load_all_tokens": load_all,
        "recall_avg_tokens": round(avg_recall),
        "search_avg_tokens": round(avg_search),
        "recall_savings_pct": round((1 - avg_recall / load_all) * 100, 1),
        "search_savings_pct": round((1 - avg_search / load_all) * 100, 1),
    }


def verifiability(paths: TalamusPaths) -> dict:
    """Fraction of notes whose source actually resolves on disk + status mix.
    The moat no vector DB has: every claim traces to a checkable source."""
    notes = load_notes(paths)
    if not notes:
        return {"notes": 0}
    statuses = [provenance_status(paths, n)["status"] for n in notes]
    ok = sum(1 for s in statuses if s == "ok")
    grounded = sum(1 for s in statuses if s != "source_missing")
    return {
        "notes": len(notes),
        "source_resolves_pct": round(grounded / len(notes) * 100, 1),
        "ok_pct": round(ok / len(notes) * 100, 1),
        "status_counts": {s: statuses.count(s) for s in sorted(set(statuses))},
    }


def cost_per_answer(
    context_tokens: int,
    answer_tokens: int,
    ingest_tokens: int,
    n_answers_amortized: int = 1000,
    price_per_1k_tokens_eur: float = 0.0,
) -> dict:
    """Pure calculation. EUR is illustrative (default 0.0 = subscription/local:
    zero marginal). Ingest cost is amortized over N answers."""
    per_answer_tokens = context_tokens + answer_tokens + ingest_tokens / max(n_answers_amortized, 1)
    return {
        "tokens_per_answer": round(per_answer_tokens),
        "eur_per_answer": round(per_answer_tokens / 1000 * price_per_1k_tokens_eur, 6),
        "note": "subscription/local engine = EUR0 marginal; EUR shown only if a price is given",
    }


def hallucination_rate(paths: TalamusPaths, cases: list[dict], ask_llm, judge_llm) -> dict:
    """Run ask on each case, then an LLM judge scores whether the answer is
    grounded in the cited notes. Lower is better; the verifiability moat in a
    number. Needs two providers (ask + judge); use a local model to stay free."""
    from talamus.ask import answer_question
    from talamus.routing import StaticRouter

    router = StaticRouter(ask_llm)
    judged = 0
    grounded = 0
    for case in cases:
        question = case["question"]
        answer = answer_question(paths, question, router)
        verdict = judge_llm.complete(
            "You are a strict fact-checker. Below is an ANSWER with a 'Fonti'/sources "
            "section. Reply with exactly one word: GROUNDED if every claim is supported "
            "by those sources, or HALLUCINATED if anything is unsupported.\n\n"
            f"ANSWER:\n{answer}"
        )
        judged += 1
        if "GROUNDED" in verdict.upper() and "HALLUCINATED" not in verdict.upper():
            grounded += 1
    return {
        "judged": judged,
        "grounded": grounded,
        "hallucination_rate": round(1 - grounded / judged, 3) if judged else 0.0,
    }
