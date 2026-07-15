"""Deferred judging: score a LongMemEval artifact produced with --judge none.

The ingest+answer run and the judging are deliberately separable — the local
judge (gemma4:e4b) needs ~10 GB of RAM, so on constrained machines it runs in
its own window with everything else closed. This pass reads a dated artifact,
scores every unjudged case with the calibrated ask_eval judge, and rewrites
the SAME artifact (json + md) with accuracy filled in and the judge recorded
in provenance. Idempotent: already-judged cases are left alone.

Usage:
    python benchmarks/longmemeval/judge_pass.py benchmarks/results/<date>-longmemeval.json
    [--judge gemma4:e4b]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from benchmarks.longmemeval.runner import Judge, _default_judge, _markdown


def judge_artifact(artifact_path: Path, judge_model: str, judge: Judge | None = None) -> dict:
    result = json.loads(artifact_path.read_text(encoding="utf-8"))
    score = judge or _default_judge(judge_model, artifact_path.parent)
    newly = 0
    for case in result["cases"]:
        if case.get("correct") is None:
            case["correct"] = bool(score(case["question"], case["gold_answer"], case["answer"]))
            newly += 1
    judged = [case for case in result["cases"] if case.get("correct") is not None]
    type_scores: dict[str, list[bool]] = defaultdict(list)
    for case in judged:
        type_scores[case["question_type"]].append(case["correct"])
    result["accuracy"] = sum(case["correct"] for case in judged) / len(judged) if judged else None
    result["accuracy_by_question_type"] = {
        question_type: sum(scores) / len(scores) for question_type, scores in type_scores.items()
    }
    result["provenance"]["judge"] = judge_model
    result["provenance"]["judged_cases"] = len(judged)
    artifact_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact_path.with_suffix(".md").write_text(_markdown(result), encoding="utf-8")
    print(f"judged {newly} case(s); accuracy {result['accuracy']}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a deferred LongMemEval artifact")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--judge", default="gemma4:e4b")
    args = parser.parse_args()
    if not args.artifact.is_file():
        print(f"artifact not found: {args.artifact}", file=sys.stderr)
        return 1
    judge_artifact(args.artifact, args.judge)
    return 0


if __name__ == "__main__":
    sys.exit(main())
