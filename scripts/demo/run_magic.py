from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

NOTE_TITLE = "SQLite FTS5 Porter Search Decision"
DECISION_KEYWORD = "FTS5"
QUESTION = "why did we choose FTS5?"


class FakeLLMProvider:
    """Deterministic demo provider; mirrors the tiny test fake without importing tests."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return ""


class _Completed:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def _fake_extraction_json() -> str:
    return json.dumps(
        [
            {
                "title": NOTE_TITLE,
                "aliases": ["SQLite FTS5 porter tokenizer decision", "FTS5 search index"],
                "tags": ["search", "retrieval", "benchmark", "agent-memory"],
                "summary": (
                    "The project chose SQLite FTS5 with the porter tokenizer for the search "
                    "index because the pure-trigram index misranked exact English terms."
                ),
                "retrieval_text": (
                    "FTS5 porter tokenizer SQLite search index pure trigram misranked exact "
                    "English terms nDCG 0.607 0.664 why choose FTS5 search ranking decision"
                ),
                "body_sections": {
                    "definizione": (
                        "The session decided to use SQLite FTS5 with the porter tokenizer as "
                        "the search index. The decision is about ranking exact English terms "
                        "without adding embeddings."
                    ),
                    "funzionamento": (
                        "FTS5 gives a lexical index with token-aware matching, while the "
                        "porter tokenizer normalizes English variants. That fixed the case "
                        "where a pure-trigram index over-weighted fuzzy character overlap."
                    ),
                    "quando": (
                        "Use this path when exact English technical terms matter. The "
                        "benchmark moved nDCG from 0.607 to 0.664, so the choice was backed "
                        "by measured retrieval quality rather than preference."
                    ),
                },
                "relations": [
                    {
                        "source": NOTE_TITLE,
                        "relation": "replaces",
                        "target": "Pure trigram search index",
                        "confidence": 0.82,
                    }
                ],
                "proposed_links": [],
                "supported_claims": [
                    (
                        "Chose SQLite FTS5 with the porter tokenizer for the search index "
                        "because pure trigram misranked exact English terms."
                    ),
                    "The benchmark improved nDCG from 0.607 to 0.664.",
                ],
                "confidence": 0.94,
            }
        ]
    )


def _default_transcript() -> str:
    turns = [
        {
            "role": "user",
            "content": (
                "Search quality regressed on the English benchmark. Exact technical terms "
                "like ranking, tokenizer, and FTS are landing below fuzzy matches. Please "
                "debug the index choice and leave the reasoning in the session summary."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "I compared the existing pure-trigram index against SQLite FTS5. The "
                "trigram path helps cross-language cognates, but on monolingual English it "
                "over-rewards fuzzy character overlap and misranks exact terms."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Decision: chose SQLite FTS5 with the porter tokenizer for the search "
                "index. Why: the pure-trigram index misranked exact English terms, while "
                "the benchmark improved nDCG from 0.607 to 0.664 and preserved the local, "
                "zero-embedding thesis."
            ),
        },
        {
            "role": "user",
            "content": (
                "Good. The next agent session should be able to recall that we chose FTS5 "
                "because of exact-term ranking and the measured nDCG win, not because it "
                "was convenient."
            ),
        },
    ]
    return "\n".join(json.dumps(turn, ensure_ascii=False) for turn in turns) + "\n"


def _default_diff() -> str:
    return "\n".join(
        [
            "diff --git a/src/search_index.py b/src/search_index.py",
            "--- a/src/search_index.py",
            "+++ b/src/search_index.py",
            "@@ -1,4 +1,5 @@",
            "-INDEX_BACKEND = 'trigram'",
            "+INDEX_BACKEND = 'sqlite-fts5'",
            "+TOKENIZER = 'porter'",
            " BENCHMARK_NDCG = {'trigram': 0.607, 'fts5_porter': 0.664}",
            "",
        ]
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Talamus M1 magic-demo arc.")
    parser.add_argument("--fake", action="store_true", help="run in-process with a fake engine")
    parser.add_argument("--dir", default=None, help="demo project directory")
    parser.add_argument("--keep", action="store_true", help="keep the generated demo directory")
    parser.add_argument("--engine", default=None, help="engine to pass to talamus setup")
    parser.add_argument(
        "--transcript-file",
        default=None,
        help="override the agent transcript; disables the default fake diff for gate tests",
    )
    return parser


def _scene(number: int, title: str) -> None:
    print()
    print(f"{number}. {title}")


def _run_cli(command: list[str], *, stdin: str | None = None, capture: bool = False) -> str:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if capture:
        result = subprocess.run(
            command,
            input=stdin,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            check=False,
        )
        output = result.stdout or ""
        print(output, end="")
    else:
        result = subprocess.run(command, input=stdin, text=True, env=env, check=False)
        output = ""
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}")
    return output


def _setup_args(root: Path, engine: str | None) -> list[str]:
    args = ["setup", "--root", str(root), "--capture", "yes"]
    if engine:
        args.extend(["--engine", engine])
    return args


def _write_session_fixture(root: Path, transcript_file: str | None) -> tuple[Path, str]:
    transcript_path = root / "agent-session.jsonl"
    if transcript_file:
        transcript = Path(transcript_file).read_text(encoding="utf-8")
        diff = ""
    else:
        transcript = _default_transcript()
        diff = _default_diff()
    transcript_path.write_text(transcript, encoding="utf-8")
    (root / "agent.diff").write_text(diff, encoding="utf-8")
    print(f"   transcript: {transcript_path}")
    print(f"   diff fixture: {root / 'agent.diff'}")
    return transcript_path, diff


def _tail_capture_log(root: Path, lines: int = 8) -> str:
    path = root / ".talamus" / "logs" / "capture.log"
    if not path.is_file():
        return "(capture.log missing)\n"
    tail = path.read_text(encoding="utf-8").splitlines()[-lines:]
    return "\n".join(tail) + ("\n" if tail else "")


def _note_titles(root: Path) -> list[str]:
    titles: list[str] = []
    cache = root / ".talamus" / "cache" / "notes"
    for path in sorted(cache.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        title = str(data.get("title", "")).strip()
        if title:
            titles.append(title)
    return titles


def _assert_recall_contains_note(recall_output: str, titles: list[str]) -> None:
    for title in titles:
        if title in recall_output:
            return
    joined = ", ".join(titles) or "(no notes)"
    raise RuntimeError(f"recall did not cite the note born in scene 2: {joined}")


def _run_fake_hook(root: Path, transcript_path: Path, diff: str, llm: FakeLLMProvider) -> int:
    # Only two seams are faked: the engine (hook-run builds its own router, so
    # main(llm=...) cannot reach it) and git (the demo dir is not a repo). The
    # index, registry, and storage paths run for real — TALAMUS_HOME is already
    # redirected into the demo dir, so nothing leaks.
    from talamus.cli import lifecycle
    from talamus.routing import StaticRouter

    old_router_for = lifecycle._router_for
    old_subprocess_run = lifecycle.subprocess.run
    old_stdin = sys.stdin
    try:
        lifecycle._router_for = lambda _root: StaticRouter(llm)
        lifecycle.subprocess.run = lambda *args, **kwargs: _Completed(stdout=diff)
        sys.stdin = io.StringIO(
            json.dumps({"transcript_path": str(transcript_path), "cwd": str(root)})
        )
        return lifecycle._cmd_hook_run(root)
    finally:
        lifecycle._router_for = old_router_for
        lifecycle.subprocess.run = old_subprocess_run
        sys.stdin = old_stdin


def _run_fake_setup(talamus_main, root: Path, engine: str | None, llm: FakeLLMProvider) -> int:
    return talamus_main(_setup_args(root, engine), llm=llm)


def _run_fake(root: Path, engine: str | None, transcript_file: str | None, start: float) -> int:
    os.environ["TALAMUS_HOME"] = str(root / "talamus-demo-home")

    from talamus.cli import main as talamus_main

    fake = FakeLLMProvider([_fake_extraction_json()])

    _scene(1, "A project gets a memory.")
    if _run_fake_setup(talamus_main, root, engine, fake) != 0:
        return 1

    _scene(2, "An agent works; the session ends.")
    transcript_path, diff = _write_session_fixture(root, transcript_file)
    if _run_fake_hook(root, transcript_path, diff, fake) != 0:
        return 1

    _scene(3, "A note was born.")
    print(_tail_capture_log(root), end="")
    titles = _note_titles(root)
    if not titles:
        print("No note was born: below worth-remembering gate.")
        return 1
    if (
        talamus_main(["search", DECISION_KEYWORD, "--root", str(root), "--scope", "project-only"])
        != 0
    ):
        return 1

    _scene(4, "A fresh session recalls.")
    recall = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = recall
        code = talamus_main(["recall", QUESTION, "--root", str(root), "--scope", "project-only"])
    finally:
        sys.stdout = old_stdout
    recall_output = recall.getvalue()
    print(recall_output, end="")
    if code != 0:
        return 1
    _assert_recall_contains_note(recall_output, titles)

    elapsed = max(1, round(time.perf_counter() - start))
    _scene(5, "The memory survived the session boundary.")
    print(f"Your agent remembered. Locally. €0. ({elapsed}s)")
    return 0


def _run_real(root: Path, engine: str | None, transcript_file: str | None, start: float) -> int:
    _scene(1, "A project gets a memory.")
    _run_cli(["talamus", *_setup_args(root, engine)])

    _scene(2, "An agent works; the session ends.")
    transcript_path, _diff = _write_session_fixture(root, transcript_file)
    payload = json.dumps({"transcript_path": str(transcript_path), "cwd": str(root)})
    _run_cli(["talamus", "hook-run", "--root", str(root)], stdin=payload)

    _scene(3, "A note was born.")
    print(_tail_capture_log(root), end="")
    titles = _note_titles(root)
    if not titles:
        print("No note was born: below worth-remembering gate.")
        return 1
    _run_cli(
        ["talamus", "search", DECISION_KEYWORD, "--root", str(root), "--scope", "project-only"],
        capture=True,
    )

    _scene(4, "A fresh session recalls.")
    recall_output = _run_cli(
        ["talamus", "recall", QUESTION, "--root", str(root), "--scope", "project-only"],
        capture=True,
    )
    _assert_recall_contains_note(recall_output, titles)
    print()
    print("Full cited answer:")
    _run_cli(
        ["talamus", "ask", QUESTION, "--root", str(root), "--scope", "project-only"],
        capture=True,
    )

    elapsed = max(1, round(time.perf_counter() - start))
    _scene(5, "The memory survived the session boundary.")
    print(f"Your agent remembered. Locally. €0. ({elapsed}s)")
    return 0


def _run(args: argparse.Namespace, root: Path, start: float) -> int:
    root.mkdir(parents=True, exist_ok=True)
    print("Talamus M1 magic demo: your agent remembers across sessions, by itself.")
    print(f"Project: {root}")
    try:
        if args.fake:
            return _run_fake(root, args.engine, args.transcript_file, start)
        return _run_real(root, args.engine, args.transcript_file, start)
    except RuntimeError as exc:
        print(f"demo failed: {exc}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    start = time.perf_counter()
    if args.dir:
        return _run(args, Path(args.dir).resolve(), start)
    if args.keep:
        root = Path(tempfile.mkdtemp(prefix="talamus-magic-demo-"))
        return _run(args, root, start)
    with tempfile.TemporaryDirectory(prefix="talamus-magic-demo-") as tmp:
        return _run(args, Path(tmp), start)


if __name__ == "__main__":
    raise SystemExit(main())
