"""Command-line entry point for the LongMemEval adapter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmarks.longmemeval.runner import (  # noqa: E402
    CostConfirmationRequired,
    run_longmemeval,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the LongMemEval benchmark")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(".bench-data/longmemeval/longmemeval_s.json"),
    )
    parser.add_argument("--engine", default="claude-cli")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--yes", action="store_true", help="confirm estimated LLM cost")
    parser.add_argument("--judge", default="gemma4:e4b")
    parser.add_argument("--out", type=Path, default=Path("benchmarks/results"))
    args = parser.parse_args(argv)

    try:
        run_longmemeval(
            args.dataset,
            engine=args.engine,
            limit=args.limit,
            out_dir=args.out,
            judge_model=args.judge,
            yes=args.yes,
        )
    except (CostConfirmationRequired, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
