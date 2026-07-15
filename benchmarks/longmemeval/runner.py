"""Run LongMemEval against fresh, isolated Talamus brains."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from benchmarks.ask_eval.judges import CachingJudge, correctness_verdict
from benchmarks.ask_eval.timeout_llm import TimeoutLLM
from benchmarks.longmemeval.loader import load_dataset
from talamus.adapters.llm import OllamaProvider
from talamus.ask import answer_question
from talamus.config import TalamusConfig, save_config
from talamus.errors import EngineLimitReached
from talamus.ingest import remember_session
from talamus.paths import TalamusPaths
from talamus.routing import EngineRouter, Router

RouterFactory = Callable[[str], Router]
Judge = Callable[[str, str, str], bool]

_REPO_ROOT = Path(__file__).resolve().parents[2]


class CostConfirmationRequired(RuntimeError):
    """Raised before any LLM work when the caller has not confirmed the cost."""


def _git_head() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _default_judge(judge_model: str, out_dir: Path) -> Judge:
    # Match ask-eval's calibrated local judge: deterministic, no thinking tokens,
    # and a tiny output budget because the shared parser only needs one label.
    provider = OllamaProvider(
        judge_model,
        options={"num_predict": 16, "temperature": 0.0},
        think=False,
    )
    cached = CachingJudge(
        TimeoutLLM(provider),
        out_dir / ".longmemeval-judge-cache.json",
    )

    def judge(question: str, gold: str, answer: str) -> bool:
        return correctness_verdict(answer, question, gold, cached) == "correct"

    return judge


def _transcript(session: list[dict], date: str) -> str:
    turns = "\n".join(f"{turn['role'].upper()}: {turn['content']}" for turn in session)
    return f"Session date: {date}\n{turns}"


def _estimate_cost(cases: list[dict]) -> None:
    questions = len(cases)
    sessions = sum(len(case["haystack_sessions"]) for case in cases)
    average = sessions / questions if questions else 0.0
    print(
        f"Cost estimate: {questions} questions x {average:.1f} average sessions = up to "
        f"{sessions} LLM extraction calls + {questions} answer calls; "
        f"also {questions} judge calls.",
        flush=True,
    )


def _markdown(result: dict) -> str:
    provenance = result["provenance"]
    lines = [
        "# LongMemEval benchmark",
        "",
        f"commit `{provenance['git']}` | {provenance['generated_at']} | "
        f"{result['total_questions']} questions",
        "",
        f"- Dataset: `{provenance['dataset']}`",
        f"- Engine: `{provenance['engine']}`",
        f"- Judge: `{provenance['judge']}`",
        f"- Limit: {provenance['limit']}",
        f"- Ingest mode: `{provenance['ingest_mode']}`",
        "",
        "| metric | value |",
        "| --- | ---: |",
        "| Judge accuracy | "
        + (
            f"{result['accuracy']:.3f}"
            if result["accuracy"] is not None
            else "deferred (judge=none)"
        )
        + " |",
        f"| Exact-contains rate | {result['exact_contains_rate']:.3f} |",
        f"| Sessions ingested | {result['sessions_ingested']} |",
        f"| Sessions skipped by gate | {result['sessions_skipped_by_gate']} |",
        "",
        "## Accuracy by question type",
        "",
        "| question type | accuracy |",
        "| --- | ---: |",
    ]
    for question_type, accuracy in sorted(result["accuracy_by_question_type"].items()):
        lines.append(f"| {question_type} | {accuracy:.3f} |")
    return "\n".join(lines) + "\n"


def _write_artifacts(result: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d")
    offset = int(result["provenance"].get("offset", 0) or 0)
    suffix = f"-from{offset}" if offset else ""
    json_path = out_dir / f"{stamp}-longmemeval{suffix}.json"
    markdown_path = json_path.with_suffix(".md")
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(result), encoding="utf-8")
    return json_path, markdown_path


def run_longmemeval(
    dataset_path: Path,
    engine: str,
    limit: int,
    out_dir: Path,
    judge_model: str = "gemma4:e4b",
    ingest_mode: str = "sessions",
    yes: bool = False,
    offset: int = 0,
    router_factory: RouterFactory | None = None,
    judge: Judge | None = None,
) -> dict:
    """Run the first `limit` cases and write dated JSON and Markdown artifacts."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if ingest_mode != "sessions":
        raise ValueError("ingest_mode must be 'sessions'")

    dataset_path = Path(dataset_path)
    out_dir = Path(out_dir)
    if offset < 0:
        raise ValueError("offset must be non-negative")
    selected = load_dataset(dataset_path)[offset : offset + limit]
    _estimate_cost(selected)
    if not yes:
        raise CostConfirmationRequired(
            "LongMemEval aborted before LLM work. Pass yes=True (CLI: --yes) to confirm cost."
        )

    # judge_model="none" defers judging: answers are still recorded in the
    # artifact, so a later judge pass can score them when the local judge has
    # RAM headroom (it needs ~10 GB); exact_contains stays as an instant signal.
    score = (
        judge
        if judge is not None
        else (None if judge_model == "none" else _default_judge(judge_model, out_dir))
    )
    cases: list[dict] = []
    type_scores: dict[str, list[bool]] = defaultdict(list)
    sessions_ingested = 0
    sessions_skipped = 0

    interrupted: str | None = None

    def _build_result() -> dict:
        total = len(cases)
        judged = [case for case in cases if case["correct"] is not None]
        accuracy_by_type = {
            question_type: sum(scores) / len(scores)
            for question_type, scores in type_scores.items()
        }
        return {
            "provenance": {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "git": _git_head(),
                "engine": engine,
                "judge": judge_model,
                "limit": limit,
                "offset": offset,
                "dataset": dataset_path.name,
                "ingest_mode": ingest_mode,
                "interrupted": interrupted,
            },
            "total_questions": total,
            "accuracy": (
                (sum(case["correct"] for case in judged) / len(judged)) if judged else None
            ),
            "accuracy_by_question_type": accuracy_by_type,
            "exact_contains_rate": (
                sum(case["exact_contains"] for case in cases) / total if total else 0.0
            ),
            "sessions_ingested": sessions_ingested,
            "sessions_skipped_by_gate": sessions_skipped,
            "cases": cases,
        }

    for position, item in enumerate(selected):
        try:
            with tempfile.TemporaryDirectory(prefix="talamus-longmemeval-") as temp_dir:
                paths = TalamusPaths(Path(temp_dir))
                paths.ensure_directories()
                config = replace(TalamusConfig.default(), llm_provider=engine)
                save_config(paths.config_path, config)
                router = router_factory(engine) if router_factory else EngineRouter(config)

                case_ingested = 0
                case_skipped = 0
                for session, date in zip(
                    item["haystack_sessions"], item["haystack_dates"], strict=True
                ):
                    ingest_result = remember_session(paths, _transcript(session, date), "", router)
                    if ingest_result.get("skipped", False):
                        case_skipped += 1
                    else:
                        case_ingested += 1

                answer = answer_question(paths, item["question"], router)
        except EngineLimitReached as exc:
            # a benchmark run pins ONE engine (provenance), so the fallback
            # chain deliberately does not apply: save everything done so far
            # and stop cleanly — relaunch later with --offset to continue.
            interrupted = str(exc)
            print(f"engine limit at question {offset + position} — saving partial results")
            break
        correct = bool(score(item["question"], item["answer"], answer)) if score else None
        exact_contains = item["answer"].casefold() in answer.casefold()
        question_type = item["question_type"]
        if correct is not None:
            type_scores[question_type].append(correct)
        sessions_ingested += case_ingested
        sessions_skipped += case_skipped
        cases.append(
            {
                "question_id": item["question_id"],
                "question_type": question_type,
                "question": item["question"],
                "gold_answer": item["answer"],
                "answer": answer,
                "correct": correct,
                "exact_contains": exact_contains,
                "sessions_ingested": case_ingested,
                "sessions_skipped_by_gate": case_skipped,
            }
        )
        # incremental persistence: a crash or limit never loses finished work
        _write_artifacts(_build_result(), out_dir)
        print(
            f"question {offset + position} done "
            f"({case_ingested} sessions in, {case_skipped} gated)",
            flush=True,
        )

    result = _build_result()
    json_path, markdown_path = _write_artifacts(result, out_dir)
    print(f"report: {json_path}", flush=True)
    print(f"report: {markdown_path}", flush=True)
    return result
