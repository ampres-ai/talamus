from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from talamus.adapters.llm import engine_command
from talamus.cli._common import (
    _ALL_COMMANDS,
    _detect_engine,
    _print_json,
    _router_for,
)
from talamus.config import TalamusConfig, load_config, save_config
from talamus.demo import create_demo_brain
from talamus.ingest import remember_session
from talamus.paths import TalamusPaths
from talamus.registry import (
    register_brain,
)
from talamus.routing import Router
from talamus.scan import (
    build_plan,
    format_plan,
)
from talamus.services.backup import export_brain, import_brain_archive
from talamus.services.diagnostics import inspect_diagnostics
from talamus.services.engines import choose_default_engine, engine_hint, list_engines
from talamus.services.integrations import (
    build_hook_snippet,
    install_capture_hook,
    install_mcp_config,
    install_mcp_config_codex,
    install_mcp_config_cursor,
)
from talamus.services.readiness import ReadinessReport, inspect_readiness
from talamus.store import reindex


def _should_verify_engine(verify: bool | None, router: Router | None) -> bool:
    """Explicit flags always win. The AUTO default probes only a real terminal
    session (stdin AND stdout are ttys) with no injected router: scripts, CI,
    harnesses and tests must never fire a live engine call they did not ask for."""
    if verify is not None:
        return verify
    return router is None and sys.stdin.isatty() and sys.stdout.isatty()


def _verify_engine(root: Path, chosen: str, router: Router | None) -> None:
    """One tiny live probe (A1/D3): declare the engine working only after it
    answered. Failure never aborts setup — brain/MCP/hook are still valid —
    but it must be loud and actionable."""
    from talamus.errors import EngineFailed, EngineLimitReached, EngineNotFound
    from talamus.routing import TaskClass

    print("     Verifying the engine with one tiny call...")
    try:
        llm = (router or _router_for(root)).for_task(TaskClass.QUERY_EXPANSION)
        answer = llm.complete("Reply with exactly: ok")
    except (EngineFailed, EngineNotFound, EngineLimitReached) as exc:
        hint = engine_hint(chosen)  # the hints map lives in services.engines (shared with the UI)
        print(f"     engine '{chosen}' NOT verified: {exc}", file=sys.stderr)
        print(f"     fix: {hint}", file=sys.stderr)
        return
    print(f"     engine verified: '{chosen}' answered ({answer.strip()[:20] or 'empty reply'})")


def _cmd_setup(
    root: Path,
    engine: str | None,
    capture: str = "ask",
    router: Router | None = None,
    verify: bool | None = None,
) -> int:
    """One-command onboarding (Fase R4): the coding-agent subscription you
    already pay for becomes a personal + agentic memory, in minutes."""
    print("Talamus setup\n")
    engines = list_engines()
    engine_ids = [item.provider for item in engines if item.available or item.needs_secret]
    chosen = engine or choose_default_engine()
    print(f"1/4  Engines detected: {', '.join(engine_ids)}")
    print(f"     Using: {chosen} (change it with --engine or from Settings)\n")
    code = _cmd_init(root, chosen, "project")
    if code != 0:
        return code
    if _should_verify_engine(verify, router):
        _verify_engine(root, chosen, router)
    print()
    print("2/4  Connecting your agent (MCP)...")
    _cmd_mcp_install(root)
    print()
    print("3/4  Session capture (the memory that grows on its own):")
    _print_capture_consent_copy(root)
    if _capture_consented(capture):
        result = install_capture_hook(root)
        if not result.success:
            print(result.message, file=sys.stderr)
            return 1
        print(f"     {result.message}")
    else:
        print("     Skipped. Enable it any time with: talamus hook --install")
    print()
    print("4/4  What there is to learn in this folder (plan, zero cost):")
    plan = build_plan(root, profile="all")
    print(format_plan(plan))
    print()
    print("Done. Your memory is alive:")
    print('  talamus ask "..."        a question with a cited answer')
    print("  talamus scan . --yes     compile the repo into the brain (after the plan above)")
    print("  talamus ui               the graphical workbench")
    return 0


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


def _cmd_export(root: Path, out_file: str) -> int:
    result = export_brain(root, out_file)
    if not result.success:
        print(result.message, file=sys.stderr)
        return 1
    print(result.message)
    return 0


def _cmd_import(out_file: str, root: Path) -> int:
    result = import_brain_archive(out_file, root)
    if not result.success:
        print(result.message, file=sys.stderr)
        return 1
    print(result.message)
    return 0


def _cmd_init(root: Path, engine: str | None = None, scope_kind: str = "project") -> int:
    paths = TalamusPaths(root)
    paths.ensure_directories()
    created = not paths.config_path.exists()
    if created:
        provider = engine or _detect_engine()
        save_config(paths.config_path, replace(TalamusConfig.default(), llm_provider=provider))
    print(f"initialized talamus project at {root}")
    if created:
        config = load_config(paths.config_path)
        command = engine_command(config.llm_provider)
        found = command is None or shutil.which(command) is not None
        print(f"engine: {config.llm_provider} ({'found' if found else 'not on PATH'})")
    brain_type = "central" if scope_kind == "global" else "project"
    info = register_brain(root, brain_type=brain_type)
    print(f"registered as '{info.name}' ({info.type})")
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


def _cmd_mcp_install(root: Path, agent: str = "auto") -> int:
    """One command, every agent (D7.2). auto = Claude Code always, Cursor when
    the project has a .cursor dir, codex when its CLI is on PATH. An agent the
    user names explicitly must succeed; an auto-detected one may just report."""
    if agent in ("claude", "cursor", "codex"):
        result = {
            "claude": lambda: install_mcp_config(root),
            "cursor": lambda: install_mcp_config_cursor(root),
            "codex": install_mcp_config_codex,
        }[agent]()
        if not result.success:
            print(result.message, file=sys.stderr)
            return 1
        print(result.message)
        return 0
    code = 0
    claude_result = install_mcp_config(root)
    if not claude_result.success:
        print(claude_result.message, file=sys.stderr)
        code = 1
    else:
        print(f"Claude Code: {claude_result.message}")
    if agent == "all" or (root / ".cursor").is_dir():
        cursor_result = install_mcp_config_cursor(root)
        if not cursor_result.success:
            print(cursor_result.message, file=sys.stderr)
            code = 1
        else:
            print(f"Cursor: {cursor_result.message}")
    if agent == "all" or shutil.which("codex") is not None:
        codex_result = install_mcp_config_codex()
        if not codex_result.success:
            # a MISSING codex is a skip even under "all"; a broken one is an error
            if codex_result.code == "codex_not_found":
                print(f"codex: skipped ({codex_result.message})")
            else:
                print(codex_result.message, file=sys.stderr)
                code = 1
        else:
            print(f"codex: {codex_result.message}")
    return code


def _print_capture_consent_copy(root: Path) -> None:
    """The D6 consent copy: name the data, the destination, and the audit trail
    BEFORE asking. Keep it honest and complete — this is the privacy contract."""
    print("     When an agent session ends, a SessionEnd hook can send Talamus:")
    print("       - the session transcript")
    print("       - the git diff of the working tree")
    print("     Only sessions that pass the worth-remembering gate become notes,")
    print(f"     stored locally in THIS brain ({root}).")
    print("     Nothing leaves your machine beyond calls to your configured LLM.")
    print("     Every capture decision is logged to .talamus/logs/capture.log.")
    print("     The hook is one SessionEnd entry in .claude/settings.json.")


def _capture_consented(capture: str) -> bool:
    if capture == "yes":
        return True
    if capture == "no":
        return False
    if not sys.stdin.isatty():
        print("     (non-interactive run: not installing without consent)")
        return False
    try:
        answer = input("     Install the capture hook? [y/N] ")
    except EOFError:
        print("     (no input available: not installing without consent)")
        return False
    return answer.strip().lower() in ("y", "yes")


def _cmd_hook(root: Path, install: bool = False) -> int:
    if install:
        installed = install_capture_hook(root)
        if not installed.success:
            print(installed.message, file=sys.stderr)
            return 1
        print(installed.message)
        return 0
    result = build_hook_snippet(root)
    if not result.success or result.data is None:
        print(result.message, file=sys.stderr)
        return 1
    print("Add to your Claude Code settings (.claude/settings.json):")
    print(json.dumps(result.data.settings, indent=2))
    print("or run: talamus hook --install")
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
    remember_session(TalamusPaths(root), transcript, diff, _router_for(root))
    return 0


def _cmd_status(
    root: Path, json_out: bool = False, readiness: ReadinessReport | None = None
) -> int:
    paths = TalamusPaths(root)
    missing = [p for p in paths.required_directories() if not p.exists()]
    not_directories = [p for p in paths.required_directories() if p.exists() and not p.is_dir()]
    config_exists = paths.config_path.exists()
    healthy = config_exists and not missing and not not_directories
    if json_out:
        if readiness is None:
            readiness = inspect_readiness(root=str(root))
        _print_json(
            {
                "ok": healthy,
                "config_exists": config_exists,
                "missing": [str(p) for p in missing],
                "not_directories": [str(p) for p in not_directories],
                "readiness": readiness.to_dict(),
            }
        )
        return 0 if healthy else 1
    if not healthy:
        if not config_exists:
            print(f"missing config: {paths.config_path}", file=sys.stderr)
        for path in missing:
            print(f"missing directory: {path}", file=sys.stderr)
        for path in not_directories:
            print(f"not a directory: {path}", file=sys.stderr)
        return 1
    print("talamus project status ok")
    return 0


def _cmd_status_json(
    root: str | None = None, brain: str | None = None, use_global: bool = False
) -> int:
    readiness = inspect_readiness(root=root, brain=brain, use_global=use_global)
    return _cmd_status(Path(str(readiness.root)), json_out=True, readiness=readiness)


def _cmd_doctor(root: Path) -> int:
    result = inspect_diagnostics(root)
    report = result.data
    if report is None:
        print(result.message, file=sys.stderr)
        return 1
    if not result.success:
        print(result.message, file=sys.stderr)
        return 1
    print(f"brain: {report.root}")
    print(f"storage: {report.storage_provider}")
    print(f"pdf converter: {report.pdf_converter}")
    ocr = (
        "none (planned)"
        if report.ocr_provider in ("", "none")
        else f"{report.ocr_provider}/{report.ocr_model}"
    )
    print(f"ocr: {ocr}")
    print(f"llm: {report.llm_provider} [{report.llm_status}]")
    print(f"graph: {report.graph_provider}")
    print(f"search: {report.search_provider}")
    print(f"notes: {report.notes}")
    print(f"index backend: {report.index_backend} ({report.index_bytes:,} bytes)")
    if report.overview_built:
        print(f"overview: built ({report.overview_domains} domains)")
    else:
        print("overview: not built — run `talamus overview`")
    print("cache: ok" if report.cache_current else "cache: stale — run `talamus reindex`")
    return 0


def _cmd_reindex(root: Path, json_out: bool) -> int:
    result = reindex(TalamusPaths(root))
    if json_out:
        _print_json(result)
    else:
        print(f"reindexed {result['reindexed']} notes")
    return 0
