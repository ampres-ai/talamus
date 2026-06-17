"""Run the end-to-end ASK evaluation on a real brain corpus.

Fair answer-quality shootout: each retrieval system → shared generator
(gemini-cli) → independent judge (ollama gemma4) → faithfulness / correctness /
context-hit / honest-refusal. Plus our REAL product ask (answer_question, with
the ontology-built overview routing) and the ontology ON/OFF ablation.

  python -m benchmarks.ask_eval.run --queries 12
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmarks.ask_eval.pipeline import evaluate_answers  # noqa: E402
from benchmarks.shootout.corpora.judged import JudgedCorpus, corpus_from_brain  # noqa: E402
from benchmarks.shootout.report import provenance  # noqa: E402


def _negatives(eval_path: str) -> list[dict]:
    data = json.loads(Path(eval_path).read_text(encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data
    return [c for c in cases if not c.get("relevant")]


def _subset(corpus: JudgedCorpus, n: int | None) -> JudgedCorpus:
    """Stratified cap: round-robin across categories (the qid prefix before the
    trailing -NNN), so a small N still spans direct/vague/cross and both
    languages. A plain sorted()[:n] picks only the alphabetically-first
    categories (cross+direct) and silently drops the vague queries where Talamus
    differs most — that bias understated the ask eval."""
    if not n or n >= len(corpus.queries):
        return corpus
    groups: dict[str, list[str]] = {}
    for qid in sorted(corpus.queries):
        cat = qid.rsplit("-", 1)[0]  # "direct-en-003" -> "direct-en"
        groups.setdefault(cat, []).append(qid)
    kept: list[str] = []
    while len(kept) < n and any(groups.values()):
        for cat in sorted(groups):
            if groups[cat] and len(kept) < n:
                kept.append(groups[cat].pop(0))
    return JudgedCorpus(
        docs=corpus.docs,
        queries={q: corpus.queries[q] for q in kept},
        qrels={q: corpus.qrels[q] for q in kept},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="End-to-end ask evaluation")
    parser.add_argument("--brain", default=r"C:\dev\_talamus_book")
    parser.add_argument("--eval", default="")
    parser.add_argument("--queries", type=int, default=12, help="cap (0 = all)")
    parser.add_argument("--gen-engine", default="gemini-cli")
    parser.add_argument("--gen-model", default="gemini-3.1-flash-lite")
    # Judge default: local gemma4:e4b. RS6 calibration measured ~1s/call with a
    # one-word output cap (num_predict) -> local-primary is viable AND free, and
    # it is a DIFFERENT family from the gemini generator (no self-flattery).
    # Pass --cross-judge-engine codex-cli to also measure inter-judge agreement.
    parser.add_argument("--judge-engine", default="ollama")
    parser.add_argument("--judge-model", default="gemma4:e4b")
    parser.add_argument("--cross-judge-engine", default="")
    parser.add_argument("--cross-judge-model", default="")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--max-negatives", type=int, default=0, help="cap negatives (0 = all)")
    parser.add_argument("--ablation", action="store_true", help="ontology ON/OFF on the real ask")
    args = parser.parse_args(argv)

    from talamus.adapters.llm import build_provider

    eval_path = args.eval or str(Path(args.brain) / "eval-cases-book.json")
    corpus = _subset(corpus_from_brain(args.brain, eval_path), args.queries or None)
    negatives = _negatives(eval_path)
    if args.max_negatives:
        negatives = negatives[: args.max_negatives]
    from benchmarks.ask_eval.judges import CachingJudge
    from benchmarks.ask_eval.timeout_llm import TimeoutLLM

    def _build_judge(engine: str, model: str):
        # local ollama judge uses HTTP options: cap output (the verdict is ONE
        # word) + temperature 0 for determinism + think=False (gemma4:e4b is a
        # reasoning model; with thinking on the reply budget is spent on hidden
        # tokens and the verdict never reaches `response`). Other engines as-is.
        from talamus.adapters.llm import OllamaProvider

        if engine == "ollama":
            return OllamaProvider(
                model, options={"num_predict": 16, "temperature": 0.0}, think=False
            )
        return build_provider(engine, model)

    results_dir = _REPO_ROOT / "benchmarks" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # hard 90s/call timeout: gemini-cli can hang past subprocess timeouts on Windows
    gen = TimeoutLLM(build_provider(args.gen_engine, args.gen_model))
    judge = CachingJudge(
        TimeoutLLM(_build_judge(args.judge_engine, args.judge_model)),
        results_dir / ".judge-cache.json",
    )
    cross_judge = None
    if args.cross_judge_engine:
        cross_judge = CachingJudge(
            TimeoutLLM(
                _build_judge(args.cross_judge_engine, args.cross_judge_model or args.gen_model)
            ),
            results_dir / ".cross-judge-cache.json",
        )

    if args.ablation:
        from benchmarks.ask_eval.ontology_ablation import evaluate_ontology_ablation

        print(f"ontology ablation on the real ask: {len(corpus.queries)} queries", flush=True)
        res = evaluate_ontology_ablation(args.brain, corpus, gen, judge)
        for variant in ("ontology_on", "ontology_off"):
            m = res[variant]
            print(
                f"{variant:13} context_hit={m['context_hit']:.3f} "
                f"faithfulness={m['faithfulness']:.3f} correctness={m['answer_correctness']:.3f} "
                f"routes={m['routes']}",
                flush=True,
            )
        out_dir = _REPO_ROOT / "benchmarks" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        import time as _t

        (out_dir / f"{_t.strftime('%Y-%m-%d')}-ask-ablation.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 0
    print(
        f"{corpus.n_docs} docs, {len(corpus.queries)} queries, {len(negatives)} negatives",
        flush=True,
    )
    print(
        f"gen={args.gen_engine}/{args.gen_model}  judge={args.judge_engine}/{args.judge_model}",
        flush=True,
    )

    from benchmarks.shootout.systems.bm25_system import BM25System
    from benchmarks.shootout.systems.talamus_system import TalamusSearch, TalamusSmart
    from benchmarks.shootout.systems.vectordb_system import VectorDBSystem

    systems = [
        ("bm25", BM25System()),
        ("vectordb", VectorDBSystem()),
        ("talamus-search", TalamusSearch()),
        ("talamus-smart", TalamusSmart(build_provider(args.gen_engine, args.gen_model))),
    ]
    results: dict = {"systems": {}}
    for i, (name, system) in enumerate(systems):
        m = evaluate_answers(
            system,
            corpus,
            gen,
            judge,
            k=args.k,
            negatives=negatives,
            cross_judge=cross_judge if i == 0 else None,
        )
        results["systems"][name] = m
        agree = ""
        if "faithfulness_agreement" in m:
            agree = (
                f" [x-judge agree faith={m['faithfulness_agreement']:.2f} "
                f"corr={m['correctness_agreement']:.2f} n={m['agreement_n']}]"
            )
        print(
            f"{name:16} context_hit={m['context_hit']:.3f} faithfulness={m['faithfulness']:.3f} "
            f"correctness={m['answer_correctness']:.3f} refusal={m.get('honest_refusal', 0):.3f}"
            f"{agree}",
            flush=True,
        )

    out = {"provenance": provenance(_REPO_ROOT, {"gen": args.gen_model, "judge": args.judge_model}),
           **results}  # fmt: skip
    out_dir = _REPO_ROOT / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    import time

    path = out_dir / f"{time.strftime('%Y-%m-%d')}-ask-eval.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
