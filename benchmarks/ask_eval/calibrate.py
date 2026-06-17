"""Time the local judge on THIS machine, then recommend judge roles.

Run BEFORE committing to local-primary vs invert (the brainstorm 'calibrate
then decide' gate). Each call mimics a real one-word faithfulness verdict."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_PROMPT = (
    "You are a strict fact-checker. Reply with ONE word: GROUNDED or HALLUCINATED.\n\n"
    "CONTEXT:\nThe sky scatters blue light.\n\nANSWER:\nThe sky is blue."
)


def calibrate(judge_llm, n: int = 5, threshold_s: float = 8.0) -> dict:
    start = time.perf_counter()
    replies = [judge_llm.complete(_PROMPT) for _ in range(n)]
    elapsed = time.perf_counter() - start
    per_call = elapsed / max(n, 1)
    # also verify the judge returns a parseable verdict, not just that it is fast
    # (a thinking model can return empty-but-fast — that would silently sink the eval)
    nonempty = sum(1 for r in replies if r.strip())
    return {
        "calls": n,
        "seconds_per_call": round(per_call, 2),
        "nonempty_replies": nonempty,
        "sample_reply": replies[0].strip()[:40] if replies else "",
        "threshold_s": threshold_s,
        "recommend": "local-primary" if per_call < threshold_s else "invert",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate the local judge")
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=8.0)
    args = parser.parse_args(argv)
    from talamus.adapters.llm import OllamaProvider

    judge = OllamaProvider(args.model, options={"num_predict": 16, "temperature": 0.0}, think=False)
    out = calibrate(judge, n=args.n, threshold_s=args.threshold)
    print(
        f"gemma judge: {out['seconds_per_call']}s/call over {out['calls']} calls "
        f"({out['nonempty_replies']}/{out['calls']} non-empty, e.g. {out['sample_reply']!r}) "
        f"-> recommend {out['recommend']} (threshold {out['threshold_s']}s)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
