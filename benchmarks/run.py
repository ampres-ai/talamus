"""Single entry point for the benchmark tiers.

python benchmarks/run.py --tier ci         # deterministic, free, every push
python benchmarks/run.py --tier shootout --yes   # real competitors + LLM (paid)
"""

from __future__ import annotations

import argparse
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


def _run_shootout(yes: bool) -> int:
    if not yes:
        print("Full shootout runs real competitors + LLM expansion (paid).")
        print("  systems: talamus-search, talamus-smart, bm25, (vectordb/mem0 in later phases)")
        print("  corpus:  BEIR scifact (downloaded once)")
        print("  Estimate: ~1 LLM call per query for talamus-smart; embeddings build for vectordb.")
        print("  Confirm with:  python benchmarks/run.py --tier shootout --yes")
        return 0
    print("Full shootout: wire BEIR + bm25 + talamus-smart here (next plan).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Talamus benchmark suite")
    parser.add_argument("--tier", choices=["ci", "shootout", "corpus"], default="ci")
    parser.add_argument("--yes", action="store_true", help="confirm a paid tier")
    parser.add_argument("--out", default="benchmarks/results", help="results directory")
    args = parser.parse_args(argv)
    if args.tier == "ci":
        return _run_ci(Path(args.out))
    if args.tier == "shootout":
        return _run_shootout(args.yes)
    print("corpus tier: implemented in the large-corpus phase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
