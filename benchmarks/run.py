"""Single entry point for the benchmark tiers.

python benchmarks/run.py --tier ci         # deterministic, free, every push
python benchmarks/run.py --tier shootout --yes   # real competitors + LLM (paid)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow `python benchmarks/run.py` (script dir on path) as well as
# `python -m benchmarks.run` (repo root on path): ensure the repo root is importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmarks.shootout.corpora.judged import JudgedCorpus  # noqa: E402
from benchmarks.shootout.report import write_report  # noqa: E402
from benchmarks.shootout.runner import run_shootout  # noqa: E402
from benchmarks.shootout.systems.talamus_system import TalamusSearch  # noqa: E402

_CI_CORPUS = JudgedCorpus(
    docs=[
        ("d1", "Quantization", "reduce the bits of model weights to save memory and cost"),
        ("d2", "Reranking", "reorder candidate documents by relevance after retrieval"),
        ("d3", "Hallucination", "a model states facts that are not grounded in any source"),
    ],
    queries={"q1": "quantization memory", "q2": "model invents false facts"},
    qrels={"q1": {"d1": 1}, "q2": {"d3": 1}},
)


def _run_ci(out_dir: Path) -> int:
    result = run_shootout([TalamusSearch()], _CI_CORPUS, k=3)
    for name, row in result["systems"].items():
        print(f"{name}: recall@k={row['recall_at_k']:.3f} hit={row['hit_rate']:.3f}")
    write_report(result, {"talamus": "dev"}, out_dir, "ci")
    return 0


def _subset_queries(corpus: JudgedCorpus, n: int | None) -> JudgedCorpus:
    """Keep all docs but cap the query set (cost control). Deterministic order."""
    if n is None or n >= len(corpus.queries):
        return corpus
    kept = sorted(corpus.queries)[:n]
    return JudgedCorpus(
        docs=corpus.docs,
        queries={q: corpus.queries[q] for q in kept},
        qrels={q: corpus.qrels[q] for q in kept if q in corpus.qrels},
    )


def _build_systems(engine: str, model: str, smart: bool = True) -> list:
    from benchmarks.shootout.systems.bm25_system import BM25System
    from benchmarks.shootout.systems.talamus_system import TalamusSearch, TalamusSmart
    from talamus.adapters.llm import build_provider

    systems: list = [TalamusSearch(), BM25System()]
    if smart:  # the LLM tier (1 call/query); skip for a free, deterministic full-set run
        systems.insert(1, TalamusSmart(build_provider(engine, model)))
    try:  # the dense-RAG competitor — included only if its (heavy) deps are present
        import faiss  # noqa: F401
        import sentence_transformers  # noqa: F401

        from benchmarks.shootout.systems.dense_multilingual import MultilingualDenseSystem
        from benchmarks.shootout.systems.vectordb_system import VectorDBSystem

        systems.append(VectorDBSystem())
        systems.append(MultilingualDenseSystem())  # the multilingual steelman
    except ImportError:
        print("  (vectordb skipped: install faiss-cpu + sentence-transformers)", flush=True)
    return systems


def _run_shootout(
    yes: bool, dataset: str, n_queries: int | None, engine: str, model: str, smart: bool = True
) -> int:
    from benchmarks.shootout.corpora.judged import load_beir

    if not yes:
        cap = n_queries if n_queries is not None else "all"
        print("Full shootout runs real competitors + LLM expansion (paid).")
        print("  systems: talamus-search, talamus-smart, bm25 (vectordb/mem0 later)")
        print(f"  corpus:  BEIR {dataset} (downloaded once); queries: {cap}")
        print(f"  Estimate: ~{cap} LLM expansion calls (talamus-smart, {engine}/{model}), cached.")
        print(
            f"  Confirm with:  python benchmarks/run.py --tier shootout --yes "
            f"--dataset {dataset} --queries {n_queries or 0}"
        )
        return 0
    if dataset == "book":
        from benchmarks.shootout.corpora.judged import corpus_from_brain

        brain = os.environ.get("TALAMUS_BENCH_BRAIN", r"C:\dev\_talamus_book")
        eval_path = os.environ.get("TALAMUS_BENCH_EVAL", str(Path(brain) / "eval-cases-book.json"))
        print(f"Loading brain corpus from {brain}...", flush=True)
        corpus = _subset_queries(corpus_from_brain(brain, eval_path), n_queries)
    else:
        print(f"Loading BEIR {dataset}...", flush=True)
        corpus = _subset_queries(load_beir(dataset), n_queries)
    print(f"  {corpus.n_docs} docs, {len(corpus.queries)} judged queries", flush=True)
    systems = _build_systems(engine, model, smart=smart)
    result = run_shootout(systems, corpus, k=10)
    for name, row in result["systems"].items():
        print(
            f"{name:16} recall@10={row['recall_at_k']:.3f} ndcg={row['ndcg_at_k']:.3f} "
            f"mrr={row['mrr']:.3f} hit={row['hit_rate']:.3f} p50={row['latency_ms_p50']:.1f}ms",
            flush=True,
        )
    paths = write_report(
        result,
        {"talamus": "dev", "engine": f"{engine}/{model}", "dataset": dataset},
        Path("benchmarks/results"),
        f"shootout-{dataset}",
    )
    print(f"report: {paths['md']}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Talamus benchmark suite")
    parser.add_argument("--tier", choices=["ci", "shootout", "corpus", "one-screen"], default="ci")
    parser.add_argument("--yes", action="store_true", help="confirm a paid tier")
    parser.add_argument("--out", default="benchmarks/results", help="results directory")
    parser.add_argument(
        "--results",
        default="benchmarks/results",
        help="committed artifacts directory (the one-screen tier reads, never writes, it)",
    )
    parser.add_argument("--dataset", default="scifact", help="BEIR dataset for the shootout")
    parser.add_argument("--queries", type=int, default=0, help="cap judged queries (0 = all)")
    parser.add_argument("--engine", default="gemini-cli", help="LLM engine for talamus-smart")
    parser.add_argument("--model", default="gemini-3.1-flash-lite", help="LLM model")
    parser.add_argument(
        "--no-smart", action="store_true", help="skip the LLM tier (free, full-set)"
    )
    args = parser.parse_args(argv)
    n_queries = args.queries or None
    if args.tier == "ci":
        return _run_ci(Path(args.out))
    if args.tier == "one-screen":
        from benchmarks.one_screen import run_one_screen

        return run_one_screen(Path(args.results), Path(args.out))
    if args.tier == "shootout":
        return _run_shootout(
            args.yes, args.dataset, n_queries, args.engine, args.model, smart=not args.no_smart
        )
    print("corpus tier: implemented in the large-corpus phase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
