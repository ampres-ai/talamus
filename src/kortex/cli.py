from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kortex.adapters.llm import ClaudeCliProvider
from kortex.ask import answer_question
from kortex.config import KortexConfig, load_config, save_config
from kortex.ingest import ingest_file
from kortex.paths import KortexPaths
from kortex.store import reindex


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
    paths = KortexPaths(root)
    paths.ensure_directories()
    if not paths.config_path.exists():
        save_config(paths.config_path, KortexConfig.default())
    print(f"initialized kortex project at {root}")
    return 0


def _cmd_status(root: Path) -> int:
    paths = KortexPaths(root)
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
    print("kortex project status ok")
    return 0


def _cmd_doctor(root: Path) -> int:
    paths = KortexPaths(root)
    if not paths.config_path.exists():
        print("kortex project is not initialized; run `kortex init`", file=sys.stderr)
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


def _cmd_ingest(root: Path, file: str, llm) -> int:
    result = ingest_file(KortexPaths(root), Path(file), llm)
    print(f"ingerite {result['notes_written']} schede da {result['source']}")
    return 0


def _cmd_ask(root: Path, question: str, llm) -> int:
    print(answer_question(KortexPaths(root), question, llm))
    return 0


def _cmd_reindex(root: Path) -> int:
    result = reindex(KortexPaths(root))
    print(f"reindicizzate {result['reindexed']} schede")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kortex", description="Local-first knowledge compiler.")
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
    return parser


def main(argv: list[str] | None = None, llm=None) -> int:
    _ensure_utf8_output()
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "init":
        return _cmd_init(root)
    if args.command == "status":
        return _cmd_status(root)
    if args.command == "doctor":
        return _cmd_doctor(root)
    if args.command == "reindex":
        return _cmd_reindex(root)
    provider = llm if llm is not None else ClaudeCliProvider()
    if args.command == "ingest":
        return _cmd_ingest(root, args.file, provider)
    if args.command == "ask":
        return _cmd_ask(root, args.question, provider)
    raise ValueError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
