from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

from talamus import __version__
from talamus.adapters.llm import LLMProvider, build_provider
from talamus.ask import answer_question
from talamus.config import TalamusConfig, load_config, load_or_default, save_config
from talamus.consolidate import apply_consolidation, find_duplicates
from talamus.correct import apply_correction, verify_note
from talamus.demo import create_demo_brain
from talamus.domains import build_overview, load_overview
from talamus.errors import TalamusError
from talamus.eval import evaluate, load_cases, search_retriever
from talamus.ingest import ingest_path, remember_session
from talamus.log import configure
from talamus.paths import TalamusPaths
from talamus.recall import concept_neighbors, read_note_text, recall_context, search_notes
from talamus.relations import list_relations, prune_relations
from talamus.store import cache_is_current, reindex
from talamus.timeline import note_as_of, note_history

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


def _cmd_ui(root: Path) -> int:
    try:
        from talamus.ui.app import run_app
    except ImportError:
        print("UI needs the 'ui' extra: pip install talamus[ui]", file=sys.stderr)
        return 1
    run_app(TalamusPaths(root))
    return 0


_ALL_COMMANDS = (
    "init demo ui status doctor reindex ingest consolidate verify ask overview search read history "
    "recall neighbors relations remember eval quickstart brains where export import completion mcp "
    "hook hook-run"
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


def _cmd_demo(root: Path) -> int:
    paths = TalamusPaths(root)
    if not paths.config_path.exists():
        save_config(
            paths.config_path, replace(TalamusConfig.default(), llm_provider=_detect_engine())
        )
    count = create_demo_brain(paths)
    print(f"demo brain ready at {root} ({count} notes)")
    print('try:  talamus search "embedding"  ·  talamus read "Embedding"')
    print('      talamus neighbors "Embedding"')
    return 0


def _cmd_mcp_install(root: Path) -> int:
    config_file = root / ".mcp.json"
    data: dict = {}
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data.setdefault("mcpServers", {})["talamus"] = {
        "command": "talamus-mcp",
        "args": ["--root", str(root)],
    }
    config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"wrote talamus MCP server to {config_file}")
    return 0


def _cmd_hook(root: Path) -> int:
    snippet = {
        "hooks": {
            "SessionEnd": [
                {"hooks": [{"type": "command", "command": f"talamus hook-run --root {root}"}]}
            ]
        }
    }
    print("Add to your Claude Code settings (.claude/settings.json):")
    print(json.dumps(snippet, indent=2))
    return 0


def _cmd_hook_run(root: Path) -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    transcript_path = payload.get("transcript_path", "")
    if not transcript_path or not Path(transcript_path).is_file():
        return 0
    transcript = Path(transcript_path).read_text(encoding="utf-8")
    cwd = payload.get("cwd") or str(Path.cwd())
    try:
        diff = subprocess.run(
            ["git", "diff", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=30
        ).stdout
    except (subprocess.SubprocessError, OSError):
        diff = ""
    remember_session(TalamusPaths(root), transcript, diff, _provider_for(root))
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


def _cmd_ingest(root: Path, target: str, llm: LLMProvider, json_out: bool) -> int:
    result = ingest_path(TalamusPaths(root), target, llm)
    if json_out:
        _print_json(result)
    elif "files" in result:
        print(
            f"ingerite {result['notes_written']} schede da {result['files']} file "
            f"({result['skipped']} invariati saltati)"
        )
        for failure in result.get("failed", []):
            print(f"  ! saltato {failure['file']}: {failure['error']}")
    else:
        print(f"ingerite {result['notes_written']} schede da {result['source']}")
    return 0


def _cmd_consolidate(root: Path, do_apply: bool, llm: LLMProvider, json_out: bool) -> int:
    paths = TalamusPaths(root)
    if do_apply:
        merged = apply_consolidation(paths, llm)
        if json_out:
            _print_json({"merged": merged})
        else:
            print(f"consolidate: merged {merged} note(s)")
        return 0
    groups = find_duplicates(paths, llm)
    if json_out:
        _print_json(groups)
        return 0
    if not groups:
        print("no duplicate concepts found")
        return 0
    for group in groups:
        others = [m for m in group["members"] if m != group["canonical"]]
        print(f"- keep '{group['canonical']}'  <=  {', '.join(others)}")
    print("\nrun `talamus consolidate --apply` to merge")
    return 0


def _cmd_verify(root: Path, title: str, do_apply: bool, llm: LLMProvider, json_out: bool) -> int:
    paths = TalamusPaths(root)
    if do_apply:
        corrected = apply_correction(paths, title, llm)
        if json_out:
            _print_json({"corrected": corrected})
        else:
            print(f"verify: {'corrected' if corrected else 'no correction needed for'} '{title}'")
        return 0
    result = verify_note(paths, title, llm)
    if json_out:
        _print_json(result)
        return 0
    if not result.get("found"):
        print(f"scheda non trovata: {title}", file=sys.stderr)
        return 1
    if not result.get("checked"):
        print(f"no source on disk to check for '{title}'")
        return 0
    if result.get("ok", True):
        print(f"'{title}' looks faithful to its source")
        return 0
    print(f"'{title}' may need a correction:")
    print(f"  summary -> {result.get('summary', '')}")
    print("run `talamus verify <title> --apply` to apply it")
    return 0


def _cmd_overview(root: Path, llm: LLMProvider, json_out: bool, rebuild: bool) -> int:
    paths = TalamusPaths(root)
    if rebuild or not paths.overview_file.exists():
        domains = build_overview(paths, llm)
    else:
        domains = load_overview(paths)
    if json_out:
        _print_json(domains)
        return 0
    if not domains:
        print("no notes yet (ingest something first)")
        return 0
    for domain in domains:
        print(f"## {domain['name']}  ({len(domain['members'])} note)")
        if domain.get("description"):
            print(f"   {domain['description']}")
    return 0


def _cmd_ask(root: Path, question: str, llm: LLMProvider, json_out: bool) -> int:
    answer = answer_question(TalamusPaths(root), question, llm)
    if json_out:
        _print_json({"answer": answer})
    else:
        print(answer)
    return 0


def _cmd_eval(root: Path, cases_file: str, k: int, json_out: bool) -> int:
    path = Path(cases_file)
    if not path.is_file():
        print(f"cases file not found: {cases_file}", file=sys.stderr)
        return 1
    cases = load_cases(path)
    if not cases:
        print("no valid cases (need entries with question + relevant[])", file=sys.stderr)
        return 1
    report = evaluate(cases, search_retriever(TalamusPaths(root)), k=k)
    if json_out:
        _print_json(report.to_dict())
    else:
        print(report.format_table())
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


def _cmd_search(root: Path, query: str, json_out: bool, limit: int = 5) -> int:
    results = search_notes(TalamusPaths(root), query, limit=limit)
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


def _cmd_history(root: Path, title: str, as_of: str | None, json_out: bool) -> int:
    paths = TalamusPaths(root)
    if as_of:
        version = note_as_of(paths, title, as_of)
        if json_out:
            _print_json(version or {})
        elif version:
            print(f"[{version.get('updated_at', '?')}] {version.get('summary', '')}")
        else:
            print(f"no version of '{title}' as of {as_of}", file=sys.stderr)
        return 0 if version else 1
    versions = note_history(paths, title)
    if json_out:
        _print_json(versions)
        return 0
    if not versions:
        print(f"scheda non trovata: {title}", file=sys.stderr)
        return 1
    for version in versions:
        print(f"[{version.get('updated_at', '?')}] {version.get('summary', '')}")
    return 0


def _cmd_recall(root: Path, question: str, json_out: bool, limit: int = 5) -> int:
    context = recall_context(TalamusPaths(root), question, limit=limit)
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


def _cmd_relations(root: Path, prune: float | None, json_out: bool) -> int:
    paths = TalamusPaths(root)
    if prune is not None:
        removed = prune_relations(paths, prune)
        if json_out:
            _print_json({"pruned": removed})
        else:
            print(f"pruned {removed} relation(s) below confidence {prune}")
        return 0
    rels = list_relations(paths)
    if json_out:
        _print_json(rels)
        return 0
    if not rels:
        print("no relations")
        return 0
    for rel in rels:
        print(f"{rel['source']} --[{rel['relation']} {rel['confidence']:.2f}]--> {rel['target']}")
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
    parser.add_argument("--version", action="version", version=f"talamus {__version__}")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", parents=[common], help="initialize a brain here")
    init.add_argument("--engine", default=None, help="LLM engine (else auto-detected).")
    sub.add_parser("demo", parents=[common], help="create a small example brain")
    sub.add_parser("ui", parents=[common], help="launch the desktop UI (needs the 'ui' extra)")
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
    mcp = sub.add_parser("mcp", parents=[common], help="set up the MCP server config (.mcp.json)")
    mcp.add_argument("action", nargs="?", default="install", choices=["install"])
    sub.add_parser("hook", parents=[common], help="print the Claude Code capture-hook config")
    sub.add_parser("hook-run", parents=[common], help="run the capture hook (reads stdin)")

    ingest = sub.add_parser("ingest", parents=[common], help="add a file, folder, or URL")
    ingest.add_argument("target", help="a file, a folder (recursive), or a URL")
    consolidate = sub.add_parser("consolidate", parents=[common], help="merge duplicate concepts")
    consolidate.add_argument("--apply", action="store_true", help="actually merge (default: list)")
    verify = sub.add_parser("verify", parents=[common], help="check a note against its source")
    verify.add_argument("title")
    verify.add_argument("--apply", action="store_true", help="apply the correction")
    overview = sub.add_parser("overview", parents=[common], help="show the domain overview")
    overview.add_argument("--rebuild", action="store_true", help="re-induce the domains")
    ask = sub.add_parser("ask", parents=[common], help="ask the brain (cited answer)")
    ask.add_argument("question")
    search = sub.add_parser("search", parents=[common], help="find relevant notes")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5, help="max results (default 5)")
    read = sub.add_parser("read", parents=[common], help="print a note by title")
    read.add_argument("title")
    history = sub.add_parser("history", parents=[common], help="show a note's past versions")
    history.add_argument("title")
    history.add_argument("--as-of", default=None, help="version current at this ISO time")
    recall = sub.add_parser("recall", parents=[common], help="retrieve context for a question")
    recall.add_argument("question")
    recall.add_argument("--limit", type=int, default=5, help="max notes of context (default 5)")
    ev = sub.add_parser("eval", parents=[common], help="measure retrieval quality on a cases file")
    ev.add_argument("--cases", required=True, help='JSON: [{"question","relevant":[titles]}]')
    ev.add_argument("-k", type=int, default=5, help="cutoff for recall@k (default 5)")
    neighbors = sub.add_parser("neighbors", parents=[common], help="show a concept's connections")
    neighbors.add_argument("concept")
    relations = sub.add_parser("relations", parents=[common], help="list/prune typed relations")
    relations.add_argument(
        "--prune", type=float, default=None, metavar="MIN", help="drop below MIN"
    )
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
        if command == "demo":
            return _cmd_demo(root)
        if command == "ui":
            return _cmd_ui(root)
        if command == "mcp":
            return _cmd_mcp_install(root)
        if command == "hook":
            return _cmd_hook(root)
        if command == "hook-run":
            return _cmd_hook_run(root)
        if command == "status":
            return _cmd_status(root)
        if command == "doctor":
            return _cmd_doctor(root)
        if command == "reindex":
            return _cmd_reindex(root, json_out)
        if command == "search":
            return _cmd_search(root, args.query, json_out, args.limit)
        if command == "read":
            return _cmd_read(root, args.title, json_out)
        if command == "history":
            return _cmd_history(root, args.title, args.as_of, json_out)
        if command == "recall":
            return _cmd_recall(root, args.question, json_out, args.limit)
        if command == "eval":
            return _cmd_eval(root, args.cases, args.k, json_out)
        if command == "neighbors":
            return _cmd_neighbors(root, args.concept, json_out)
        if command == "relations":
            return _cmd_relations(root, args.prune, json_out)
        provider = llm if llm is not None else _provider_for(root)
        if command == "ingest":
            return _cmd_ingest(root, args.target, provider, json_out)
        if command == "consolidate":
            return _cmd_consolidate(root, args.apply, provider, json_out)
        if command == "verify":
            return _cmd_verify(root, args.title, args.apply, provider, json_out)
        if command == "overview":
            return _cmd_overview(root, provider, json_out, args.rebuild)
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
