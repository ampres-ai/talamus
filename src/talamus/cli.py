from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

from talamus.adapters.llm import LLMProvider, build_provider
from talamus.ask import answer_question
from talamus.config import TalamusConfig, load_config, load_or_default, save_config
from talamus.errors import TalamusError
from talamus.ingest import ingest_file, remember_session
from talamus.log import configure
from talamus.paths import TalamusPaths
from talamus.recall import concept_neighbors, read_note_text, recall_context, search_notes
from talamus.store import cache_is_current, reindex

_ENGINE_COMMANDS: dict[str, str | None] = {
    "claude-cli": "claude",
    "ollama": "ollama",
    "codex": "codex",
    "gemini": "gemini",
    "api": None,
}


def _engine_command(provider: str) -> str | None:
    return _ENGINE_COMMANDS.get(provider, provider)


def _detect_engine() -> str:
    """Pick an LLM engine that is actually installed; fall back to claude-cli."""
    for provider in ("claude-cli", "ollama"):
        command = _ENGINE_COMMANDS[provider]
        if command and shutil.which(command):
            return provider
    return "claude-cli"


def _global_home() -> Path:
    """Container for global (named) brains; override with TALAMUS_HOME."""
    return Path(os.environ.get("TALAMUS_HOME") or Path.home() / "talamus")


def _find_project_root(start: Path) -> Path | None:
    for directory in [start, *start.parents]:
        if (directory / "talamus.json").exists():
            return directory
    return None


def _resolve_root(root: str | None, brain: str | None, use_global: bool) -> Path:
    """Which brain to use: --root > --brain > --global > project (upward) > global default."""
    if root is not None:
        return Path(root).resolve()
    if brain is not None:
        return (_global_home() / brain).resolve()
    if use_global:
        return (_global_home() / "default").resolve()
    project = _find_project_root(Path.cwd().resolve())
    return project if project is not None else (_global_home() / "default").resolve()


def _provider_for(root: Path) -> LLMProvider:
    config = load_or_default(TalamusPaths(root).config_path)
    return build_provider(config.llm_provider, config.llm_model)


def _ensure_utf8_output() -> None:
    """Forza l'output UTF-8 dove possibile (la console Windows altrimenti storpia gli accenti)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _cmd_panel(root: Path) -> int:
    paths = TalamusPaths(root)
    print("Talamus — local-first knowledge compiler\n")
    if not paths.config_path.exists():
        print(f"No brain here ({root}). Create one:")
        print("  talamus init                  initialize a brain in this folder")
        print('\nThen:  talamus ingest <file>   ·   talamus ask "..."')
    else:
        n_notes = len(list(paths.notes.glob("*.md"))) if paths.notes.exists() else 0
        print(f"Brain: {root}  ·  {n_notes} notes\n")
        print("Common commands:")
        print("  talamus ingest <file>         add a document")
        print('  talamus ask "<question>"      cited answer from your brain')
        print('  talamus search "<query>"      find relevant notes (cheap)')
        print("  talamus doctor                health check")
    print("\n`talamus <command> -h` for options  ·  `talamus quickstart` for the basics")
    return 0


def _cmd_quickstart() -> int:
    print(
        "Talamus in a few commands:\n"
        "  talamus init                    create a brain in the current folder\n"
        "  talamus ingest notes.md         turn a document into linked concept-notes\n"
        '  talamus ask "how does X work?"  get a cited answer from your brain\n'
        '  talamus search "X"              list relevant notes (token-cheap)\n'
        '  talamus neighbors "X"           see what a concept connects to\n'
        "\nBrowse notes/ as an Obsidian vault. Connect agents via MCP (see README)."
    )
    return 0


_ALL_COMMANDS = (
    "init status doctor reindex ingest ask search read recall neighbors "
    "remember quickstart brains where export import completion"
)


def _cmd_completion(shell: str) -> int:
    if shell == "zsh":
        print(f"#compdef talamus\n_arguments '1:command:({_ALL_COMMANDS})'")
    else:
        print(
            "_talamus() {\n"
            f'  COMPREPLY=($(compgen -W "{_ALL_COMMANDS}" -- "${{COMP_WORDS[COMP_CWORD]}}"))\n'
            "}\n"
            "complete -F _talamus talamus"
        )
    return 0


def _cmd_brains() -> int:
    home = _global_home()
    brains = (
        [d.name for d in sorted(home.iterdir()) if (d / "talamus.json").exists()]
        if home.exists()
        else []
    )
    if not brains:
        print(f"no global brains yet (they will live under {home})")
        return 0
    for name in brains:
        print(f"- {name}")
    return 0


def _cmd_where(root: Path) -> int:
    has_brain = (root / "talamus.json").exists()
    print(f"{root}  ({'brain' if has_brain else 'no brain here'})")
    return 0


def _cmd_export(root: Path, out_file: str) -> int:
    paths = TalamusPaths(root)
    if not paths.config_path.exists():
        print(f"no brain at {root}", file=sys.stderr)
        return 1
    members = [paths.config_path, *paths.notes.rglob("*"), *paths.talamus_dir.rglob("*")]
    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as archive:
        for member in members:
            if member.is_file():
                archive.write(member, member.relative_to(root).as_posix())
    print(f"exported brain to {out_file}")
    return 0


def _cmd_import(out_file: str, root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_file) as archive:
        archive.extractall(root)
    print(f"imported brain into {root}")
    return 0


def _cmd_init(root: Path, engine: str | None = None) -> int:
    paths = TalamusPaths(root)
    paths.ensure_directories()
    created = not paths.config_path.exists()
    if created:
        provider = engine or _detect_engine()
        save_config(paths.config_path, replace(TalamusConfig.default(), llm_provider=provider))
    print(f"initialized talamus project at {root}")
    if created:
        config = load_config(paths.config_path)
        command = _engine_command(config.llm_provider)
        found = command is None or shutil.which(command) is not None
        print(f"engine: {config.llm_provider} ({'found' if found else 'not on PATH'})")
    print("next: talamus ingest <file>")
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
    except TalamusError as exc:
        print(f"config error: {paths.config_path}: {exc}", file=sys.stderr)
        return 1
    print(f"storage: {config.storage_provider}")
    print(f"pdf converter: {config.pdf_converter}")
    print(f"ocr: {config.ocr_provider}/{config.ocr_model}")
    command = _engine_command(config.llm_provider)
    engine_status = (
        "ok" if (command is None or shutil.which(command)) else f"NOT on PATH ({command})"
    )
    print(f"llm: {config.llm_provider} [{engine_status}]")
    print(f"graph: {config.graph_provider}")
    print(f"search: {config.search_provider}")
    n_notes = len(list(paths.notes.glob("*.md"))) if paths.notes.exists() else 0
    print(f"notes: {n_notes}")
    print("cache: ok" if cache_is_current(paths) else "cache: stale — run `talamus reindex`")
    return 0


def _cmd_reindex(root: Path, json_out: bool) -> int:
    result = reindex(TalamusPaths(root))
    if json_out:
        _print_json(result)
    else:
        print(f"reindicizzate {result['reindexed']} schede")
    return 0


def _cmd_ingest(root: Path, file: str, llm: LLMProvider, json_out: bool) -> int:
    result = ingest_file(TalamusPaths(root), Path(file), llm)
    if json_out:
        _print_json(result)
    else:
        print(f"ingerite {result['notes_written']} schede da {result['source']}")
    return 0


def _cmd_ask(root: Path, question: str, llm: LLMProvider, json_out: bool) -> int:
    answer = answer_question(TalamusPaths(root), question, llm)
    if json_out:
        _print_json({"answer": answer})
    else:
        print(answer)
    return 0


def _cmd_remember(
    root: Path, transcript_file: str, diff_file: str | None, llm: LLMProvider, json_out: bool
) -> int:
    transcript = Path(transcript_file).read_text(encoding="utf-8")
    diff = Path(diff_file).read_text(encoding="utf-8") if diff_file else ""
    result = remember_session(TalamusPaths(root), transcript, diff, llm)
    if json_out:
        _print_json(result)
        return 0
    if result["skipped"]:
        print("sessione saltata (sotto la soglia del gate)")
    else:
        print(f"ricordate {result['notes_written']} schede dalla sessione")
    return 0


def _cmd_search(root: Path, query: str, json_out: bool) -> int:
    results = search_notes(TalamusPaths(root), query)
    if json_out:
        _print_json(results)
        return 0
    if not results:
        print("nessuna scheda pertinente")
        return 0
    for item in results:
        print(f"- {item['title']}: {item['summary']}")
    return 0


def _cmd_read(root: Path, title: str, json_out: bool) -> int:
    text = read_note_text(TalamusPaths(root), title)
    if json_out:
        _print_json({"title": title, "found": text is not None, "markdown": text})
        return 0 if text is not None else 1
    if text is None:
        print(f"scheda non trovata: {title}", file=sys.stderr)
        return 1
    print(text)
    return 0


def _cmd_recall(root: Path, question: str, json_out: bool) -> int:
    context = recall_context(TalamusPaths(root), question)
    if json_out:
        _print_json({"context": context})
    else:
        print(context)
    return 0


def _cmd_neighbors(root: Path, concept: str, json_out: bool) -> int:
    items = concept_neighbors(TalamusPaths(root), concept)
    if json_out:
        _print_json(items)
        return 0
    if not items:
        print("nessun concetto collegato")
        return 0
    for item in items:
        arrow = "->" if item["direction"] == "out" else "<-"
        print(f"{arrow} [{item['relation']}] {item['title']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root", default=None, help="Explicit brain directory (overrides scoping)."
    )
    common.add_argument("--brain", default=None, help="Named global brain under TALAMUS_HOME.")
    common.add_argument(
        "--global", dest="use_global", action="store_true", help="Use the default global brain."
    )
    common.add_argument("--verbose", action="store_true", help="Verbose diagnostics to stderr.")
    common.add_argument("--json", action="store_true", help="Machine-readable JSON output.")

    parser = argparse.ArgumentParser(prog="talamus", description="Local-first knowledge compiler.")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", parents=[common], help="initialize a brain here")
    init.add_argument("--engine", default=None, help="LLM engine (else auto-detected).")
    for name in ("status", "doctor", "reindex"):
        sub.add_parser(name, parents=[common], help=f"{name} the brain")
    sub.add_parser("quickstart", help="print the essential commands")
    sub.add_parser("brains", help="list global brains")
    sub.add_parser("where", parents=[common], help="print the resolved brain path")
    export = sub.add_parser("export", parents=[common], help="export the brain to a zip")
    export.add_argument("file")
    importer = sub.add_parser("import", parents=[common], help="import a brain from a zip")
    importer.add_argument("file")
    completion = sub.add_parser("completion", help="print a shell completion script")
    completion.add_argument("shell", nargs="?", default="bash", choices=["bash", "zsh"])

    ingest = sub.add_parser("ingest", parents=[common], help="add a document to the brain")
    ingest.add_argument("file")
    ask = sub.add_parser("ask", parents=[common], help="ask the brain (cited answer)")
    ask.add_argument("question")
    search = sub.add_parser("search", parents=[common], help="find relevant notes")
    search.add_argument("query")
    read = sub.add_parser("read", parents=[common], help="print a note by title")
    read.add_argument("title")
    recall = sub.add_parser("recall", parents=[common], help="retrieve context for a question")
    recall.add_argument("question")
    neighbors = sub.add_parser("neighbors", parents=[common], help="show a concept's connections")
    neighbors.add_argument("concept")
    remember = sub.add_parser("remember", parents=[common], help="capture an agent session")
    remember.add_argument("--transcript", required=True)
    remember.add_argument("--diff", default=None)
    return parser


def main(argv: list[str] | None = None, llm: LLMProvider | None = None) -> int:
    _ensure_utf8_output()
    args = build_parser().parse_args(argv)
    configure(getattr(args, "verbose", False))
    command = args.command
    if command is None:
        return _cmd_panel(_resolve_root(None, None, False))
    if command == "quickstart":
        return _cmd_quickstart()
    if command == "brains":
        return _cmd_brains()
    if command == "completion":
        return _cmd_completion(args.shell)

    root = _resolve_root(args.root, args.brain, args.use_global)
    json_out = bool(getattr(args, "json", False))
    try:
        if command == "where":
            return _cmd_where(root)
        if command == "export":
            return _cmd_export(root, args.file)
        if command == "import":
            return _cmd_import(args.file, root)
        if command == "init":
            return _cmd_init(root, args.engine)
        if command == "status":
            return _cmd_status(root)
        if command == "doctor":
            return _cmd_doctor(root)
        if command == "reindex":
            return _cmd_reindex(root, json_out)
        if command == "search":
            return _cmd_search(root, args.query, json_out)
        if command == "read":
            return _cmd_read(root, args.title, json_out)
        if command == "recall":
            return _cmd_recall(root, args.question, json_out)
        if command == "neighbors":
            return _cmd_neighbors(root, args.concept, json_out)
        provider = llm if llm is not None else _provider_for(root)
        if command == "ingest":
            return _cmd_ingest(root, args.file, provider, json_out)
        if command == "ask":
            return _cmd_ask(root, args.question, provider, json_out)
        if command == "remember":
            return _cmd_remember(root, args.transcript, args.diff, provider, json_out)
    except TalamusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    raise ValueError(f"unknown command {command}")


if __name__ == "__main__":
    raise SystemExit(main())
