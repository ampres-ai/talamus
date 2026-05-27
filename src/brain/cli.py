from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brain.config import BrainConfig, load_config, save_config
from brain.paths import BrainPaths


def _cmd_init(root: Path) -> int:
    paths = BrainPaths(root)
    paths.ensure_directories()
    if not paths.config_path.exists():
        save_config(paths.config_path, BrainConfig.default())
    print(f"initialized brain project at {root}")
    return 0


def _cmd_status(root: Path) -> int:
    paths = BrainPaths(root)
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
    print("brain project status ok")
    return 0


def _cmd_doctor(root: Path) -> int:
    paths = BrainPaths(root)
    if not paths.config_path.exists():
        print("brain project is not initialized; run `brain init`", file=sys.stderr)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brain", description="Local-first knowledge compiler.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "doctor"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "init":
        return _cmd_init(root)
    if args.command == "status":
        return _cmd_status(root)
    if args.command == "doctor":
        return _cmd_doctor(root)
    raise ValueError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
