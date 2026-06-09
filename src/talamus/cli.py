from __future__ import annotations

import argparse
import sys
from pathlib import Path

from talamus.adapters.llm import ClaudeCliProvider, LLMProvider
from talamus.ask import answer_question
from talamus.config import TalamusConfig, load_config, save_config
from talamus.errors import TalamusError
from talamus.ingest import ingest_file, remember_session
from talamus.log import configure
from talamus.paths import TalamusPaths
from talamus.recall import concept_neighbors, read_note_text, recall_context, search_notes
from talamus.store import reindex


def _ensure_utf8_output() -> None:
    """Forza l'output UTF-8 dove possibile (la console Windows altrimenti storpia gli accenti)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def _cmd_init(root: Path) -> int:
    paths = TalamusPaths(root)
    paths.ensure_directories()
    if not paths.config_path.exists():
        save_config(paths.config_path, TalamusConfig.default())
    print(f"initialized talamus project at {root}")
    return 0


def _cmd_status(root: Path) -> int:
    paths = TalamusPaths(root)
    missing = [p for p in paths.required_directories() if not p.exists()]
    not_directories = [p for p in paths.required_directories() if p.exists() and not p.is_dir()]
    config_exists = paths.config_path.exists()
    if missing or not_directories or not config_exists:
        if not config_exists:
            print(f"missing config: {paths.config_path}", file=sys.stderr)
        for path in missing:
            print(f"missing directory: {path}", file=sys.stderr)
        for path in not_directories:
            print(f"not a directory: {path}", file=sys.stderr)
        return 1
    print("talamus project status ok")
    return 0


def _cmd_doctor(root: Path) -> int:
    paths = TalamusPaths(root)
    if not paths.config_path.exists():
        print("talamus project is not initialized; run `talamus init`", file=sys.stderr)
        return 1
    try:
        config = load_config(paths.config_path)
    except Exception as exc:
        print(f"config error: {paths.config_path}: {exc}", file=sys.stderr)
        return 1
    print(f"storage: {config.storage_provider}")
    print(f"pdf converter: {config.pdf_converter}")
    print(f"ocr: {config.ocr_provider}/{config.ocr_model}")
    print(f"llm: {config.llm_provider}")
    print(f"graph: {config.graph_provider}")
    print(f"search: {config.search_provider}")
    return 0


def _cmd_ingest(root: Path, file: str, llm: LLMProvider) -> int:
    result = ingest_file(TalamusPaths(root), Path(file), llm)
    print(f"ingerite {result['notes_written']} schede da {result['source']}")
    return 0


def _cmd_ask(root: Path, question: str, llm: LLMProvider) -> int:
    print(answer_question(TalamusPaths(root), question, llm))
    return 0


def _cmd_remember(root: Path, transcript_file: str, diff_file: str | None, llm: LLMProvider) -> int:
    transcript = Path(transcript_file).read_text(encoding="utf-8")
    diff = Path(diff_file).read_text(encoding="utf-8") if diff_file else ""
    result = remember_session(TalamusPaths(root), transcript, diff, llm)
    if result["skipped"]:
        print("sessione saltata (sotto la soglia del gate)")
    else:
        print(f"ricordate {result['notes_written']} schede dalla sessione")
    return 0


def _cmd_reindex(root: Path) -> int:
    result = reindex(TalamusPaths(root))
    print(f"reindicizzate {result['reindexed']} schede")
    return 0


def _cmd_search(root: Path, query: str) -> int:
    results = search_notes(TalamusPaths(root), query)
    if not results:
        print("nessuna scheda pertinente")
        return 0
    for item in results:
        print(f"- {item['title']}: {item['summary']}")
    return 0


def _cmd_read(root: Path, title: str) -> int:
    text = read_note_text(TalamusPaths(root), title)
    if text is None:
        print(f"scheda non trovata: {title}", file=sys.stderr)
        return 1
    print(text)
    return 0


def _cmd_recall(root: Path, question: str) -> int:
    print(recall_context(TalamusPaths(root), question))
    return 0


def _cmd_neighbors(root: Path, concept: str) -> int:
    items = concept_neighbors(TalamusPaths(root), concept)
    if not items:
        print("nessun concetto collegato")
        return 0
    for item in items:
        arrow = "->" if item["direction"] == "out" else "<-"
        print(f"{arrow} [{item['relation']}] {item['title']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="talamus", description="Local-first knowledge compiler.")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics to stderr.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "doctor", "reindex"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("file")
    ingest.add_argument("--root", default=".")
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--root", default=".")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--root", default=".")
    read = sub.add_parser("read")
    read.add_argument("title")
    read.add_argument("--root", default=".")
    recall = sub.add_parser("recall")
    recall.add_argument("question")
    recall.add_argument("--root", default=".")
    neighbors = sub.add_parser("neighbors")
    neighbors.add_argument("concept")
    neighbors.add_argument("--root", default=".")
    remember = sub.add_parser("remember")
    remember.add_argument("--transcript", required=True)
    remember.add_argument("--diff", default=None)
    remember.add_argument("--root", default=".")
    return parser


def main(argv: list[str] | None = None, llm: LLMProvider | None = None) -> int:
    _ensure_utf8_output()
    args = build_parser().parse_args(argv)
    configure(getattr(args, "verbose", False))
    root = Path(args.root).resolve()
    try:
        if args.command == "init":
            return _cmd_init(root)
        if args.command == "status":
            return _cmd_status(root)
        if args.command == "doctor":
            return _cmd_doctor(root)
        if args.command == "reindex":
            return _cmd_reindex(root)
        if args.command == "search":
            return _cmd_search(root, args.query)
        if args.command == "read":
            return _cmd_read(root, args.title)
        if args.command == "recall":
            return _cmd_recall(root, args.question)
        if args.command == "neighbors":
            return _cmd_neighbors(root, args.concept)
        provider = llm if llm is not None else ClaudeCliProvider()
        if args.command == "ingest":
            return _cmd_ingest(root, args.file, provider)
        if args.command == "ask":
            return _cmd_ask(root, args.question, provider)
        if args.command == "remember":
            return _cmd_remember(root, args.transcript, args.diff, provider)
    except TalamusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    raise ValueError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
