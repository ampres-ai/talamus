"""The answer-quality pipeline: each retrieval system → top-k docs → the SAME
cited-answer generator → judges. Isolates retrieval's effect on the final
answer, the surface that matters most."""

from __future__ import annotations

import sys

from benchmarks.ask_eval.judges import (
    agreement,
    correctness_verdict,
    faithfulness_verdict,
    is_refusal,
)
from benchmarks.shootout.corpora.judged import JudgedCorpus


def _safe(fn, default, label, *args):
    """Never let one hung/failed LLM call sink the whole eval batch. Returns
    default on any error so the run finishes and the failure is visible."""
    try:
        return fn(*args)
    except Exception as exc:  # EngineFailed, timeouts, anything
        print(
            f"    ! {label} failed: {type(exc).__name__}: {str(exc)[:80]}",
            file=sys.stderr,
            flush=True,
        )
        return default


_ANSWER_PROMPT = (
    "Answer the QUESTION using ONLY the CONTEXT. Cite sources as [n]. If the "
    "context is not enough, say so explicitly and do not invent.\n\n"
    "QUESTION: {question}\n\nCONTEXT:\n{context}"
)


def generate_answer(question: str, contexts: list[str], gen_llm) -> str:
    """Shared cited-answer generator — identical for every system, so only
    retrieval differs."""
    if not contexts:
        return "Il contesto non contiene informazioni sufficienti."
    context = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts, start=1))
    return gen_llm.complete(_ANSWER_PROMPT.format(question=question, context=context)).strip()


def evaluate_answers(
    system,
    corpus: JudgedCorpus,
    gen_llm,
    judge_llm,
    k: int = 5,
    negatives: list[dict] | None = None,
    cross_judge=None,
    agree_n: int = 12,
) -> dict:
    """Run the system → generate → judge over the judged corpus. Returns
    faithfulness, correctness, context-hit and (on negatives) honest-refusal.

    When `cross_judge` is given, the first `agree_n` answers are also judged by
    it; inter-judge agreement (a confidence number) is reported. Pairs are kept
    aligned by only comparing items both judges actually scored."""
    text_by_id = {doc_id: text for doc_id, _title, text in corpus.docs}
    system.ingest(corpus.as_docs())
    faithful = 0
    correct = 0.0
    context_hit = 0
    n = 0
    faith_cmp_p: list[str] = []
    faith_cmp_x: list[str] = []
    corr_cmp_p: list[str] = []
    corr_cmp_x: list[str] = []
    total = len(corpus.queries)
    for i_q, (qid, question) in enumerate(corpus.queries.items(), start=1):
        relevant = set(corpus.qrels.get(qid, {}))
        ids = system.query(question, k)
        contexts = [text_by_id[i] for i in ids if i in text_by_id]
        answer = _safe(generate_answer, "", "gen", question, contexts, gen_llm)
        if any(i in relevant for i in ids):
            context_hit += 1
        reference = "\n".join(text_by_id[i] for i in relevant if i in text_by_id)
        joined_ctx = "\n\n".join(contexts)
        if answer:
            is_faithful = _safe(
                faithfulness_verdict, False, "faithful", answer, joined_ctx, judge_llm
            )
            grade = _safe(
                correctness_verdict, "wrong", "correct", answer, question, reference, judge_llm
            )
        else:
            is_faithful = False
            grade = "wrong"
        if is_faithful:
            faithful += 1
        correct += {"correct": 1.0, "partial": 0.5, "wrong": 0.0}[grade]
        if cross_judge is not None and answer and i_q <= agree_n:
            faith_cmp_p.append(str(is_faithful))
            faith_cmp_x.append(
                str(
                    _safe(
                        faithfulness_verdict, False, "x-faithful", answer, joined_ctx, cross_judge
                    )
                )
            )
            corr_cmp_p.append(grade)
            corr_cmp_x.append(
                _safe(
                    correctness_verdict,
                    "wrong",
                    "x-correct",
                    answer,
                    question,
                    reference,
                    cross_judge,
                )
            )
        n += 1
        print(f"    {system.name} q{i_q}/{total} done", flush=True)
    out = {
        "n": n,
        "context_hit": round(context_hit / n, 3) if n else 0.0,
        "faithfulness": round(faithful / n, 3) if n else 0.0,
        "answer_correctness": round(correct / n, 3) if n else 0.0,
    }
    if faith_cmp_x:
        out["faithfulness_agreement"] = agreement(faith_cmp_p, faith_cmp_x)
        out["correctness_agreement"] = agreement(corr_cmp_p, corr_cmp_x)
        out["agreement_n"] = len(faith_cmp_x)
    if negatives:
        refused = 0
        for case in negatives:
            ids = system.query(case["question"], k)
            contexts = [text_by_id[i] for i in ids if i in text_by_id]
            answer = _safe(generate_answer, "", "neg-gen", case["question"], contexts, gen_llm)
            if is_refusal(answer):
                refused += 1
        out["honest_refusal"] = round(refused / len(negatives), 3)
    return out
