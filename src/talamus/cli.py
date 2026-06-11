from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from talamus import __version__
from talamus.adapters.llm import LLMProvider, build_provider
from talamus.ask import answer_from_items, answer_question
from talamus.config import TalamusConfig, load_config, load_or_default, save_config
from talamus.consolidate import apply_consolidation, find_duplicates
from talamus.correct import apply_correction, verify_note
from talamus.demo import create_demo_brain
from talamus.domains import build_overview, load_overview
from talamus.errors import TalamusError
from talamus.eval import evaluate, load_cases, search_retriever
from talamus.federation import build_federated_index, federation_status
from talamus.ingest import ingest_path, remember_session
from talamus.jobs import JobRecord, JobStore
from talamus.log import configure
from talamus.ontology_lab import (
    deprecate_type,
    induce_candidates,
    load_schema,
    ontology_eval,
    promote_candidate,
    read_history,
    reject_candidate,
    schema_status,
    stability,
)
from talamus.paths import TalamusPaths
from talamus.recall import concept_neighbors, read_note_text, recall_context, search_notes
from talamus.registry import (
    central_brain,
    load_registry,
    register_brain,
    rename_brain,
    select_brain,
    set_brain_flag,
    talamus_home,
    unregister_brain,
)
from talamus.relations import list_relations, prune_relations
from talamus.review import ReviewQueue
from talamus.scan import (
    PROFILES,
    build_plan,
    execute_plan,
    format_plan,
    plan_from_record,
)
from talamus.scope import (
    SCOPE_POLICIES,
    ResolvedBrain,
    default_scope,
    promote_note,
    resolve_brain,
    resolve_init_root,
    scoped_context_items,
    scoped_search,
)
from talamus.store import cache_is_current, reindex
from talamus.temporal import note_timeline, parse_when
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
    return talamus_home()


def _resolve_root(root: str | None, brain: str | None, use_global: bool) -> Path:
    """Which brain to use (see talamus.scope.resolve_brain for the full order)."""
    return resolve_brain(root, brain, use_global).root


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


def _dashboard_data(resolved: ResolvedBrain) -> dict:
    from talamus.indexes import backend_info
    from talamus.store import cache_is_current as _fresh

    paths = TalamusPaths(resolved.root)
    central = central_brain()
    notes = len(list(paths.notes.glob("*.md"))) if paths.notes.exists() else 0
    sources = len(list(paths.raw.glob("*"))) if paths.raw.exists() else 0
    reviews = len(ReviewQueue(paths).list(status="pending"))
    jobs_running = sum(1 for j in JobStore(paths).list() if j.state in ("running", "queued"))
    schema = schema_status(paths)
    active_types = schema["types"].get("active", 0)
    candidates = schema["types"].get("candidate", 0)
    return {
        "brain": str(resolved.root),
        "scope": resolved.scope,
        "config_exists": paths.config_path.exists(),
        "central": str(central.root()) if central else None,
        "notes": notes,
        "sources": sources,
        "reviews": reviews,
        "indexes": {
            "fresh": _fresh(paths),
            "backend": backend_info(paths)["backend"],
        },
        "ontology": {
            "version": schema["version"],
            "active": active_types,
            "candidates": candidates,
        },
        "jobs_running": jobs_running,
        "overview_built": paths.overview_file.is_file(),
    }


def _dashboard_next(data: dict) -> list[str]:
    suggestions: list[str] = []
    if not data["config_exists"]:
        return ["talamus init", "talamus demo   (example brain, no LLM needed)"]
    if data["notes"] == 0:
        suggestions.append("talamus ingest <file>   o   talamus scan . --dry-run")
    if data["jobs_running"]:
        suggestions.append("talamus jobs list")
    if data["reviews"]:
        suggestions.append("talamus review list")
    if data["notes"] and not data["overview_built"]:
        suggestions.append("talamus overview   (build the domain map)")
    if not data["indexes"]["fresh"]:
        suggestions.append("talamus reindex   (cache is stale)")
    if not suggestions:
        suggestions.append('talamus ask "..."')
    return suggestions


def _cmd_panel(resolved: ResolvedBrain, json_out: bool = False) -> int:
    data = _dashboard_data(resolved)
    if json_out:
        _print_json({**data, "next": _dashboard_next(data)})
        return 0
    print("Talamus")
    print(f"Brain      {data['brain']}  [{data['scope']}]")
    if data["central"] and data["central"] != data["brain"]:
        print(f"Central    {data['central']}")
    if not data["config_exists"]:
        print("Stato      nessun brain qui (talamus init per crearlo)")
    else:
        print(
            f"Notes      {data['notes']}      Sources  {data['sources']}"
            f"      Reviews  {data['reviews']}"
        )
        fresh = "fresh" if data["indexes"]["fresh"] else "stale"
        onto = data["ontology"]
        ontology_label = f"v{onto['version']} ({onto['active']} active"
        ontology_label += f", {onto['candidates']} candidate)" if onto["candidates"] else ")"
        print(
            f"Indexes    {fresh} ({data['indexes']['backend']})"
            f"    Ontology {ontology_label}    Jobs {data['jobs_running']} running"
        )
    print("\nNext")
    for suggestion in _dashboard_next(data):
        print(f"  {suggestion}")
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


def _cmd_ui(root: Path, web: bool = False, port: int = 8550) -> int:
    try:
        from talamus.ui.app import run_app
    except ImportError:
        print("UI needs the 'ui' extra: pip install talamus[ui]", file=sys.stderr)
        return 1
    run_app(TalamusPaths(root), web=web, port=port)
    return 0


_ALL_COMMANDS = (
    "setup init demo ui status doctor reindex ingest scan consolidate verify ask overview search "
    "read "
    "history timeline recall neighbors relations remember eval ontology jobs review quickstart "
    "brains where export import completion mcp hook hook-run"
)

# Runners that can resume a persisted job, keyed by kind (scan registers below).
JOB_RUNNERS: dict[str, Callable[[Path, JobRecord], int]] = {}


def _cmd_setup(root: Path, engine: str | None) -> int:
    """One-command onboarding (Fase R4): the coding-agent subscription you
    already pay for becomes a personal + agentic memory, in minutes."""
    from talamus.adapters.llm import detect_engines

    print("Talamus setup\n")
    engines = detect_engines()
    chosen = engine or next((e for e in engines if e != "anthropic-api"), "claude-cli")
    print(f"1/4  Motori rilevati: {', '.join(engines)}")
    print(f"     Uso: {chosen} (cambialo con --engine o dalle Impostazioni)\n")
    code = _cmd_init(root, chosen, "project")
    if code != 0:
        return code
    print()
    print("2/4  Collego il tuo agent (MCP)...")
    _cmd_mcp_install(root)
    print()
    print("3/4  Hook di cattura sessione (per ricordare il lavoro dell'agent):")
    _cmd_hook(root)
    print()
    print("4/4  Cosa c'è da imparare in questa cartella (piano, costo zero):")
    plan = build_plan(root, profile="all")
    print(format_plan(plan))
    print()
    print("Fatto. La tua memoria è viva:")
    print('  talamus ask "..."        domanda con risposta citata')
    print("  talamus scan . --yes     compila la repo nel brain (dopo il piano qui sopra)")
    print("  talamus ui               il workbench grafico")
    return 0


def _cmd_scan(
    root: Path,
    target: str,
    llm_factory: Callable[[], LLMProvider],
    args: argparse.Namespace,
) -> int:
    json_out = bool(getattr(args, "json", False))
    plan = build_plan(
        Path(target),
        profile=args.profile,
        include=args.include or None,
        exclude=args.exclude or None,
        max_files=args.max_files,
    )
    if args.dry_run or not (args.yes or args.background):
        if json_out:
            _print_json(plan.to_dict())
        else:
            print(format_plan(plan))
            if not args.dry_run:
                print("\n(dry-run shown; pass --yes to execute or --background to queue a job)")
        return 0
    if plan.secret_flags and not args.allow_secrets:
        flagged = sorted({f["path"] for f in plan.secret_flags})
        print(
            "error: likely secrets detected; scan stopped before any LLM call\n"
            f"cause: {len(flagged)} file(s) flagged: {', '.join(flagged[:5])}\n"
            "fix: review the files, then re-run with --allow-secrets "
            "(content is redacted) or use a local provider",
            file=sys.stderr,
        )
        return 1
    if not plan.included:
        print("nothing to scan (no supported files in plan)")
        return 0
    paths = TalamusPaths(root)
    if args.background:
        store = JobStore(paths)
        record = store.create("scan", payload=plan.to_dict())
        print(f"queued scan job {record.job_id} ({len(plan.included)} files)")
        print(f"run it with:  talamus jobs resume {record.job_id}")
        return 0
    report = execute_plan(paths, plan, llm_factory())
    if json_out:
        _print_json(report)
        return 0
    print(
        f"scan {report['state']}: {report['notes_written']} schede da "
        f"{report['files']} file (job {report['job_id']})"
    )
    for failure in report["failed"]:
        print(f"  ! {failure['path']}: {failure['error']}")
    return 0


def _run_scan_job(root: Path, record: JobRecord) -> int:
    """Resume runner registered in JOB_RUNNERS for `talamus jobs resume`."""
    paths = TalamusPaths(root)
    plan = plan_from_record(record)
    report = execute_plan(paths, plan, _provider_for(root), job_record=record)
    print(
        f"scan {report['state']}: {report['notes_written']} schede da "
        f"{report['files']} file (job {report['job_id']})"
    )
    return 0


JOB_RUNNERS["scan"] = _run_scan_job


def _cmd_ontology_group(
    args: argparse.Namespace, root: Path, llm_factory: Callable[[], LLMProvider]
) -> int:
    paths = TalamusPaths(root)
    cmd = getattr(args, "ontology_cmd", None) or "status"
    json_out = bool(getattr(args, "json", False))
    if cmd == "status":
        status = schema_status(paths)
        if json_out:
            _print_json(status)
            return 0
        print(f"schema: {status['schema_id']} (v{status['version']})")
        for state, count in sorted(status["types"].items()):
            print(f"  {state}: {count}")
        cov = status["coverage"]
        print(
            f"coverage: {cov['non_related']}/{cov['edges']} archi tipizzati "
            f"({cov['non_related_share']:.0%})"
        )
        return 0
    if cmd == "induce":
        created = induce_candidates(paths, llm_factory(), min_support=args.min_support)
        if json_out:
            _print_json([c.to_dict() for c in created])
            return 0
        if not created:
            print("nessun nuovo candidato (superfici già spiegate o supporto insufficiente)")
            return 0
        print(f"{len(created)} tipi candidati indotti:")
        for candidate in created:
            print(f"  - {candidate.id}  support={candidate.support}  «{candidate.definition}»")
        print("rivedi con `talamus ontology review`, promuovi con `talamus ontology apply ID`")
        return 0
    if cmd == "review":
        schema = load_schema(paths)
        pending = [t for t in schema.relation_types if t.status == "candidate"]
        if json_out:
            _print_json([t.to_dict() for t in pending])
            return 0
        if not pending:
            print("nessun candidato in attesa")
        for rel_type in pending:
            print(f"- {rel_type.id}  support={rel_type.support} note={rel_type.distinct_notes}")
            if rel_type.definition:
                print(f"    {rel_type.definition}")
            for example in rel_type.examples[:2]:
                print(f"    es. {example}")
        return 0
    if cmd == "apply":
        ok, message = promote_candidate(paths, args.type_id, force=args.force)
        print(message if ok else f"error: {message}", file=None if ok else sys.stderr)
        return 0 if ok else 1
    if cmd == "reject":
        ok, message = reject_candidate(paths, args.type_id, getattr(args, "reason", "") or "")
        print(message if ok else f"error: {message}", file=None if ok else sys.stderr)
        return 0 if ok else 1
    if cmd == "deprecate":
        ok, message = deprecate_type(paths, args.type_id, getattr(args, "reason", "") or "")
        print(message if ok else f"error: {message}", file=None if ok else sys.stderr)
        return 0 if ok else 1
    if cmd == "eval":
        report = ontology_eval(paths, Path(args.cases), k=args.k)
        if json_out:
            _print_json(report)
            return 0
        print(
            f"baseline : recall@{report['k']} {report['baseline']['recall_at_k']}"
            f"  MRR {report['baseline']['mrr']}"
        )
        print(
            f"emergente: recall@{report['k']} {report['emergent']['recall_at_k']}"
            f"  MRR {report['emergent']['mrr']}"
        )
        print(f"lift     : recall {report['lift']['recall_at_k']:+}  MRR {report['lift']['mrr']:+}")
        cov = report["coverage"]
        print(f"coverage : {cov['non_related_share']:.0%} archi tipizzati")
        return 0
    if cmd == "stability":
        result = stability(paths, runs=args.runs)
        _print_json(result) if json_out else print(
            f"stability (Jaccard, {result['runs']} run): {result['jaccard']}"
        )
        return 0
    if cmd == "history":
        events = read_history(paths)
        if json_out:
            _print_json(events)
            return 0
        if not events:
            print("nessun evento di schema")
        for event in events:
            print(f"- {event.get('at', '?')}  {event.get('event', '?')}  {event.get('type', '')}")
        return 0
    if cmd == "export":
        _print_json(load_schema(paths).to_dict())
        return 0
    raise ValueError(f"unknown ontology command {cmd}")


def _cmd_jobs_group(args: argparse.Namespace, root: Path) -> int:
    store = JobStore(TalamusPaths(root))
    cmd = getattr(args, "jobs_cmd", None) or "list"
    json_out = bool(getattr(args, "json", False))
    if cmd == "list":
        records = store.list()
        if json_out:
            _print_json([r.to_dict() for r in records])
            return 0
        if not records:
            print("no jobs")
        for record in records:
            progress = record.progress or {}
            done = progress.get("done", "-")
            total = progress.get("total", "-")
            print(f"- {record.job_id}  {record.state}  {done}/{total}")
        return 0
    job = store.load(args.job_id)
    if job is None:
        print(f"no job '{args.job_id}'", file=sys.stderr)
        return 1
    if cmd == "status":
        if json_out:
            _print_json(job.to_dict())
            return 0
        print(f"job: {job.job_id}\nstate: {job.state}")
        for key, value in (job.progress or {}).items():
            if key != "done_items":
                print(f"{key}: {value}")
        if job.error:
            print(f"error: {job.error}")
        return 0
    if cmd == "logs":
        log = store.read_log(args.job_id)
        print(log if log else "no log")
        return 0
    if cmd == "cancel":
        if store.cancel(args.job_id):
            print(f"cancelled {args.job_id}")
            return 0
        print(f"cannot cancel '{args.job_id}' (missing or already terminal)", file=sys.stderr)
        return 1
    if cmd == "resume":
        runner = JOB_RUNNERS.get(job.kind)
        if runner is None:
            print(
                f"error: no runner available for job kind '{job.kind}'\n"
                f"cause: this kind is resumed by the feature that created it\n"
                f"fix: re-run the original command",
                file=sys.stderr,
            )
            return 1
        return runner(root, job)
    raise ValueError(f"unknown jobs command {cmd}")


def _cmd_review_group(args: argparse.Namespace, root: Path) -> int:
    queue = ReviewQueue(TalamusPaths(root))
    cmd = getattr(args, "review_cmd", None) or "list"
    json_out = bool(getattr(args, "json", False))
    if cmd == "list":
        status = None if getattr(args, "all", False) else "pending"
        items = queue.list(status=status)
        if json_out:
            _print_json([i.to_dict() for i in items])
            return 0
        if not items:
            print("review queue empty")
        for item in items:
            print(f"- {item.item_id}  [{item.kind}]  {item.status}  {item.title}")
        return 0
    entry = queue.get(args.item_id)
    if entry is None:
        print(f"no review item '{args.item_id}'", file=sys.stderr)
        return 1
    if cmd == "show":
        if json_out:
            _print_json(entry.to_dict())
            return 0
        for key, value in entry.to_dict().items():
            print(f"{key}: {value}")
        return 0
    if cmd == "apply":
        if entry.kind == "correction":
            from talamus.correct import apply_proposed_correction

            if not apply_proposed_correction(TalamusPaths(root), entry.detail):
                print(
                    f"cannot apply: note '{entry.detail.get('title')}' not found", file=sys.stderr
                )
                return 1
        applied = queue.apply(
            args.item_id, resolution="correction written" if entry.kind == "correction" else ""
        )
        if applied is None:
            print(f"'{args.item_id}' is not pending", file=sys.stderr)
            return 1
        print(f"applied {applied.item_id} ({applied.kind})")
        return 0
    if cmd == "reject":
        rejected = queue.reject(args.item_id, getattr(args, "reason", "") or "")
        if rejected is None:
            print(f"'{args.item_id}' is not pending", file=sys.stderr)
            return 1
        print(f"rejected {rejected.item_id} (kept in the log)")
        return 0
    raise ValueError(f"unknown review command {cmd}")


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


def _cmd_brains_list(json_out: bool) -> int:
    registry = load_registry()
    if json_out:
        _print_json(registry.to_dict())
        return 0
    if not registry.brains:
        print(f"no brains registered yet (registry: {talamus_home() / 'registry.json'})")
        print("  `talamus init` registers automatically;")
        print("  `talamus brains register PATH` for existing brains")
    for brain in registry.brains:
        selected = " *" if registry.selected == brain.name else ""
        flags = []
        if not brain.federated:
            flags.append("no-fed")
        if brain.sensitive:
            flags.append("sensitive")
        extra = f" [{', '.join(flags)}]" if flags else ""
        print(f"- {brain.name}{selected}  ({brain.type}){extra}  {brain.path}")
    home = talamus_home()
    if home.exists():
        unregistered = [
            d.name
            for d in sorted(home.iterdir())
            if d.is_dir() and (d / "talamus.json").exists() and load_registry().by_path(d) is None
        ]
        for name in unregistered:
            print(f"- {name}  (non registrato — `talamus brains register {home / name}`)")
    return 0


def _cmd_brains_info(name: str, json_out: bool) -> int:
    registry = load_registry()
    brain = registry.by_name(name)
    if brain is None:
        print(f"no brain named '{name}' in the registry", file=sys.stderr)
        return 1
    root = brain.root()
    notes = len(list((root / "notes").glob("*.md"))) if (root / "notes").exists() else 0
    info = {**brain.to_dict(), "notes": notes, "exists": (root / "talamus.json").exists()}
    if json_out:
        _print_json(info)
        return 0
    for key, value in info.items():
        print(f"{key}: {value}")
    return 0


def _cmd_brains_index(rebuild: bool, status_only: bool, json_out: bool) -> int:
    if status_only:
        status = federation_status()
        if json_out:
            _print_json(status)
        else:
            built = f"built {status.get('built_at')}" if status["built"] else "not built"
            print(f"federated index: {built} · rows: {status['rows']}")
        return 0
    report = build_federated_index()
    if json_out:
        _print_json(report)
        return 0
    print(f"federated index built: {report['rows']} note da {len(report['brains'])} brain")
    for entry in report["brains"]:
        skipped = f" ({entry['skipped']})" if "skipped" in entry else ""
        print(f"  - {entry['brain']}: {entry['notes']} note{skipped}")
    for warning in report["warnings"]:
        print(f"  ! {warning}")
    return 0


def _cmd_brains_group(args: argparse.Namespace) -> int:
    cmd = getattr(args, "brains_cmd", None) or "list"
    json_out = bool(getattr(args, "json", False))
    if cmd == "list":
        return _cmd_brains_list(json_out)
    if cmd == "use":
        if select_brain(args.name):
            print(f"selected brain: {args.name}")
            return 0
        print(f"no brain named '{args.name}' (see `talamus brains list`)", file=sys.stderr)
        return 1
    if cmd == "info":
        return _cmd_brains_info(args.name, json_out)
    if cmd == "rename":
        try:
            ok = rename_brain(args.old, args.new)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"renamed: {args.old} -> {args.new}" if ok else f"no brain named '{args.old}'")
        return 0 if ok else 1
    if cmd == "delete":
        if unregister_brain(args.name):
            print(f"unregistered '{args.name}' (files on disk are preserved)")
            return 0
        print(f"no brain named '{args.name}'", file=sys.stderr)
        return 1
    if cmd == "register":
        info = register_brain(Path(args.path).resolve(), args.name, args.type)
        print(f"registered '{info.name}' ({info.type}) at {info.path}")
        return 0
    if cmd == "set":
        changed = False
        for flag in ("federated", "sensitive"):
            value = getattr(args, flag, None)
            if value is not None:
                if not set_brain_flag(args.name, flag, value == "true"):
                    print(f"no brain named '{args.name}'", file=sys.stderr)
                    return 1
                changed = True
        if not changed:
            print("nothing to set (pass --federated and/or --sensitive)", file=sys.stderr)
            return 1
        print(f"updated '{args.name}'")
        return 0
    if cmd == "index":
        return _cmd_brains_index(args.rebuild, args.action == "status", json_out)
    if cmd == "promote":
        registry = load_registry()
        source = registry.by_name(args.from_brain)
        target = registry.by_name(args.to_brain)
        if source is None or target is None:
            missing = args.from_brain if source is None else args.to_brain
            print(f"no brain named '{missing}' in the registry", file=sys.stderr)
            return 1
        if promote_note(source.root(), target.root(), args.note, source.name):
            print(f"promoted '{args.note}': {source.name} -> {target.name}")
            return 0
        print(f"note '{args.note}' not found in '{source.name}'", file=sys.stderr)
        return 1
    raise ValueError(f"unknown brains command {cmd}")


def _cmd_where(resolved: ResolvedBrain, json_out: bool) -> int:
    config_exists = (resolved.root / "talamus.json").exists()
    if json_out:
        _print_json(
            {
                "resolved_root": str(resolved.root),
                "scope": resolved.scope,
                "source": resolved.source,
                "config_exists": config_exists,
            }
        )
        return 0
    print(f"{resolved.root}  ({'brain' if config_exists else 'no brain here'})")
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
        command = _engine_command(config.llm_provider)
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


def _cmd_status(root: Path, json_out: bool = False) -> int:
    paths = TalamusPaths(root)
    missing = [p for p in paths.required_directories() if not p.exists()]
    not_directories = [p for p in paths.required_directories() if p.exists() and not p.is_dir()]
    config_exists = paths.config_path.exists()
    healthy = config_exists and not missing and not not_directories
    if json_out:
        _print_json(
            {
                "ok": healthy,
                "config_exists": config_exists,
                "missing": [str(p) for p in missing],
                "not_directories": [str(p) for p in not_directories],
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
    print(f"brain: {paths.project_root}")
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
    from talamus.indexes import backend_info

    n_notes = len(list(paths.notes.glob("*.md"))) if paths.notes.exists() else 0
    print(f"notes: {n_notes}")
    info = backend_info(paths)
    print(f"index backend: {info['backend']} ({info['bytes']:,} bytes)")
    overview = load_overview(paths)
    if overview:
        print(f"overview: built ({len(overview)} domini)")
    else:
        print("overview: not built — run `talamus overview`")
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


def _cmd_verify_batch(
    root: Path, llm: LLMProvider, only_stale: bool, source: str | None, json_out: bool
) -> int:
    from talamus.correct import verify_batch

    report = verify_batch(TalamusPaths(root), llm, only_stale=only_stale, source_filter=source)
    if json_out:
        _print_json(report)
        return 0
    print(
        f"verificate {report['checked']} schede: {report['ok']} ok, "
        f"{report['corrections_proposed']} correzioni proposte, "
        f"{report['stale']} fonti stantie, {report['skipped']} saltate"
    )
    if report["corrections_proposed"] or report["stale"]:
        print("rivedi con `talamus review list`")
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


def _cmd_overview(
    root: Path, llm: LLMProvider, json_out: bool, rebuild: bool, policy: str | None = None
) -> int:
    if policy == "all":
        registry = load_registry()
        collected: list[tuple[str, list[dict]]] = []
        for brain in registry.brains:
            if not brain.federated or not (brain.root() / "talamus.json").exists():
                continue
            collected.append((brain.name, load_overview(TalamusPaths(brain.root()))))
        if json_out:
            _print_json([{"brain": name, "domains": domains} for name, domains in collected])
            return 0
        for name, brain_domains in collected:
            print(f"=== {name} ===")
            for domain in brain_domains:
                print(f"## {domain['name']}  ({len(domain.get('members', []))} note)")
        return 0
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


def _cmd_ask(
    root: Path,
    question: str,
    llm: LLMProvider,
    json_out: bool,
    policy: str | None = None,
    with_trace: bool = False,
    as_of: str | None = None,
) -> int:
    policy = policy or default_scope(root)
    trace: dict | None = {"scope": policy} if with_trace else None
    if as_of:
        when = parse_when(as_of)
        if trace is not None and when.warning:
            trace["as_of_warning"] = when.warning
        paths = TalamusPaths(root)
        items: list[dict] = []
        for hit in search_notes(paths, question, limit=5):
            version = note_as_of(paths, hit["title"], as_of)
            if version is None:
                continue  # the note did not exist yet at that time
            joiner = chr(10)
            body = joiner.join(str(v) for v in version.get("body_sections", {}).values())
            items.append(
                {
                    "route": "as-of",
                    "path": f"[as-of {as_of}] {hit['title']}",
                    "content": f"{version.get('summary', '')}{joiner}{body}",
                }
            )
        if not items:
            print(f"nessuna conoscenza nel brain alla data {as_of}")
            return 0
        answer = answer_from_items(question, items, llm, trace=trace)
        if json_out:
            temporal_payload: dict = {
                "answer": answer,
                "scope": policy,
                "as_of": when.instant_utc,
            }
            if trace is not None:
                temporal_payload["trace"] = trace
            _print_json(temporal_payload)
            return 0
        print(answer)
        return 0
    if policy == "central-only":
        central = central_brain()
        if central is None:
            print("no central brain registered (run `talamus init --global`)", file=sys.stderr)
            return 1
        answer = answer_question(TalamusPaths(central.root()), question, llm, trace=trace)
    else:
        extra: list[dict] = []
        if policy == "project+central":
            extra, _ = scoped_context_items(
                root, question, "central-only", limit=5, exclude_roots=[root]
            )
        elif policy == "all":
            extra, _ = scoped_context_items(root, question, "all", limit=5, exclude_roots=[root])
        answer = answer_question(TalamusPaths(root), question, llm, extra_items=extra, trace=trace)
    if json_out:
        payload: dict = {"answer": answer, "scope": policy}
        if trace is not None:
            payload["trace"] = trace
        _print_json(payload)
        return 0
    print(answer)
    if trace is not None:
        print("--- trace ---", file=sys.stderr)
        print(json.dumps(trace, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0


def _cmd_eval_scale(sizes_arg: str | None, json_out: bool) -> int:
    from talamus.bench import run_scale

    sizes = [int(s) for s in (sizes_arg or "100,1000,10000").split(",") if s.strip()]
    rows = run_scale(sizes)
    if json_out:
        _print_json(rows)
        return 0
    print("| note | search p50 (ms) | search p95 (ms) | backend | bytes |")
    for row in rows:
        print(
            f"| {row['n_notes']} | {row['search']['p50_ms']} | {row['search']['p95_ms']}"
            f" | {row['index']['backend']} | {row['index']['bytes']:,} |"
        )
    return 0


def _cmd_eval(
    root: Path, cases_file: str, k: int, json_out: bool, category: str | None = None
) -> int:
    path = Path(cases_file)
    if not path.is_file():
        print(f"cases file not found: {cases_file}", file=sys.stderr)
        return 1
    cases = load_cases(path, category=category)
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


def _cmd_search(
    root: Path, query: str, json_out: bool, limit: int = 5, policy: str | None = None
) -> int:
    policy = policy or default_scope(root)
    results, warnings = scoped_search(root, query, policy, limit=limit)
    if json_out:
        _print_json(results)
        return 0
    if not results:
        print("nessuna scheda pertinente")
    for item in results:
        marker = "" if item.get("scope") == "[project]" else f"{item.get('scope', '')} "
        print(f"- {marker}{item['title']}: {item['summary']}")
    for warning in warnings:
        print(f"  ! {warning}", file=sys.stderr)
    return 0


def _cmd_read(root: Path, title: str, json_out: bool, as_of: str | None = None) -> int:
    paths = TalamusPaths(root)
    if as_of:
        version = note_as_of(paths, title, as_of)
        if version is None:
            print(f"nessuna versione di '{title}' a {as_of}", file=sys.stderr)
            return 1
        if json_out:
            _print_json(version)
            return 0
        print(f"# {version.get('title', title)}  [as-of {as_of}]")
        print()
        print(version.get("summary", ""))
        print()
        for section, body in version.get("body_sections", {}).items():
            print(f"## {section.capitalize()}")
            print(body)
            print()
        return 0
    text = read_note_text(paths, title)
    if json_out:
        _print_json({"title": title, "found": text is not None, "markdown": text})
        return 0 if text is not None else 1
    if text is None:
        print(f"scheda non trovata: {title}", file=sys.stderr)
        return 1
    print(text)
    return 0


def _cmd_timeline(root: Path, title: str, json_out: bool) -> int:
    data = note_timeline(TalamusPaths(root), title)
    if json_out:
        _print_json(data)
        return 0
    print(f"Timeline di '{title}'")
    print("- storia delle transazioni (quando Talamus ha cambiato il record):")
    if not data["transaction"]:
        print("  (nessuna versione)")
    for event in data["transaction"]:
        print(f"  [{event['at']}] {event['summary']}")
    print("- validita' dei fatti (quando erano veri nel mondo rappresentato):")
    if not data["valid"]:
        print("  (nessun claim registrato)")
    for claim in data["valid"]:
        closed = f" -> {claim['to']}" if claim["to"] else ""
        marker = f"  (invalidato da: {claim['invalidated_by']})" if claim["invalidated_by"] else ""
        print(f"  [{claim['from']}{closed}] {claim['text']}{marker}")
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


def _render_scoped_items(items: list[dict]) -> str:
    return "\n".join(
        f"[{idx}] {item['path']}\n{item['content']}" for idx, item in enumerate(items, start=1)
    )


def _cmd_recall(
    root: Path, question: str, json_out: bool, limit: int = 5, policy: str | None = None
) -> int:
    policy = policy or default_scope(root)
    warnings: list[str] = []
    if policy == "central-only":
        items, warnings = scoped_context_items(root, question, "central-only", limit=limit)
        context = _render_scoped_items(items) or "Nessun contesto pertinente trovato nel brain."
    else:
        context = recall_context(TalamusPaths(root), question, limit=limit)
        if policy in ("project+central", "all"):
            sub_policy = "central-only" if policy == "project+central" else "all"
            extra, warnings = scoped_context_items(
                root, question, sub_policy, limit=limit, exclude_roots=[root]
            )
            if extra:
                context += "\n\n" + _render_scoped_items(extra)
    if json_out:
        _print_json({"context": context, "scope": policy, "warnings": warnings})
    else:
        print(context)
        for warning in warnings:
            print(f"  ! {warning}", file=sys.stderr)
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
    common.add_argument(
        "--plain",
        "--no-color",
        dest="plain",
        action="store_true",
        help="Plain output (no ANSI color; honored by default — output is already plain).",
    )
    common.add_argument("--json", action="store_true", help="Machine-readable JSON output.")

    parser = argparse.ArgumentParser(
        prog="talamus",
        description="Local-first knowledge compiler.",
        epilog=(
            "examples:\n"
            "  talamus init --scan             brain here + repo scan plan (dry-run)\n"
            '  talamus ask "come funziona X?"  cited answer from your notes\n'
            "  talamus search ontologia --all-brains\n"
            '  talamus ask "..." --as-of 2026-01 --trace\n'
            "  talamus ontology induce         grow the emergent type system"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"talamus {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    setup = sub.add_parser(
        "setup", parents=[common], help="one-command onboarding: brain + engine + MCP + hook"
    )
    setup.add_argument("--engine", default=None, help="LLM engine (else best detected)")
    init = sub.add_parser("init", parents=[common], help="initialize a brain here")
    init.add_argument("--engine", default=None, help="LLM engine (else auto-detected).")
    init.add_argument(
        "--scan", action="store_true", help="after init, show the repo scan plan (dry-run)"
    )
    init.add_argument("--profile", choices=list(PROFILES), default="all")
    sub.add_parser("demo", parents=[common], help="create a small example brain")
    ui = sub.add_parser("ui", parents=[common], help="launch the workbench (needs the 'ui' extra)")
    ui.add_argument("--web", action="store_true", help="open in the browser (test mode, F9.1)")
    ui.add_argument("--port", type=int, default=8550, help="port for --web (default 8550)")
    for name in ("status", "doctor", "reindex"):
        sub.add_parser(name, parents=[common], help=f"{name} the brain")
    sub.add_parser("quickstart", help="print the essential commands")
    brains = sub.add_parser("brains", help="manage the brain registry")
    brains_sub = brains.add_subparsers(dest="brains_cmd")
    brains_sub.add_parser("list", parents=[common], help="list registered brains")
    b_use = brains_sub.add_parser("use", parents=[common], help="select the default global brain")
    b_use.add_argument("name")
    b_info = brains_sub.add_parser("info", parents=[common], help="show one brain's record")
    b_info.add_argument("name")
    b_rename = brains_sub.add_parser("rename", parents=[common], help="rename a registered brain")
    b_rename.add_argument("old")
    b_rename.add_argument("new")
    b_delete = brains_sub.add_parser(
        "delete", parents=[common], help="unregister a brain (files are preserved)"
    )
    b_delete.add_argument("name")
    b_register = brains_sub.add_parser(
        "register", parents=[common], help="register an existing brain"
    )
    b_register.add_argument("path")
    b_register.add_argument("--name", default=None)
    b_register.add_argument("--type", default="project", choices=["project", "central", "archive"])
    b_set = brains_sub.add_parser("set", parents=[common], help="set federation/privacy flags")
    b_set.add_argument("name")
    b_set.add_argument("--federated", choices=["true", "false"], default=None)
    b_set.add_argument("--sensitive", choices=["true", "false"], default=None)
    b_index = brains_sub.add_parser(
        "index", parents=[common], help="build or inspect the federated index"
    )
    b_index.add_argument("action", nargs="?", default="build", choices=["build", "status"])
    b_index.add_argument("--rebuild", action="store_true", help="force a full rebuild")
    b_promote = brains_sub.add_parser(
        "promote", parents=[common], help="promote a note between brains"
    )
    b_promote.add_argument("note")
    b_promote.add_argument("--from", dest="from_brain", required=True)
    b_promote.add_argument("--to", dest="to_brain", default="default")
    sub.add_parser("where", parents=[common], help="print the resolved brain path")
    onto = sub.add_parser("ontology", help="the emergent type system: induce, review, promote")
    onto_sub = onto.add_subparsers(dest="ontology_cmd")
    onto_sub.add_parser("status", parents=[common], help="schema version, types, coverage")
    o_induce = onto_sub.add_parser(
        "induce", parents=[common], help="induce candidate relation types from the corpus"
    )
    o_induce.add_argument("--min-support", type=int, default=3, help="evidence per candidate")
    onto_sub.add_parser("review", parents=[common], help="list candidate types with evidence")
    o_apply = onto_sub.add_parser("apply", parents=[common], help="promote a candidate to active")
    o_apply.add_argument("type_id")
    o_apply.add_argument("--force", action="store_true", help="override promotion thresholds")
    o_reject = onto_sub.add_parser("reject", parents=[common], help="reject a candidate (kept)")
    o_reject.add_argument("type_id")
    o_reject.add_argument("--reason", default="")
    o_depr = onto_sub.add_parser("deprecate", parents=[common], help="deprecate an active type")
    o_depr.add_argument("type_id")
    o_depr.add_argument("--reason", default="")
    o_eval = onto_sub.add_parser(
        "eval", parents=[common], help="retrieval lift: fixed baseline vs active schema"
    )
    o_eval.add_argument("--cases", required=True)
    o_eval.add_argument("-k", type=int, default=5)
    o_stab = onto_sub.add_parser("stability", parents=[common], help="cluster stability (Jaccard)")
    o_stab.add_argument("--runs", type=int, default=3)
    onto_sub.add_parser("history", parents=[common], help="schema change events")
    onto_sub.add_parser("export", parents=[common], help="print the full schema JSON")
    jobs = sub.add_parser("jobs", help="inspect and control long-running jobs")
    jobs_sub = jobs.add_subparsers(dest="jobs_cmd")
    jobs_sub.add_parser("list", parents=[common], help="list jobs")
    for jobs_action in ("status", "resume", "cancel", "logs"):
        j_parser = jobs_sub.add_parser(jobs_action, parents=[common], help=f"{jobs_action} a job")
        j_parser.add_argument("job_id")
    review = sub.add_parser("review", help="review queue: pending decisions")
    review_sub = review.add_subparsers(dest="review_cmd")
    r_list = review_sub.add_parser("list", parents=[common], help="list pending review items")
    r_list.add_argument("--all", action="store_true", help="include applied/rejected items")
    for review_action in ("show", "apply"):
        r_parser = review_sub.add_parser(
            review_action, parents=[common], help=f"{review_action} a review item"
        )
        r_parser.add_argument("item_id")
    r_reject = review_sub.add_parser("reject", parents=[common], help="reject a review item")
    r_reject.add_argument("item_id")
    r_reject.add_argument("--reason", default="", help="why it was rejected (kept in the log)")
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
    scan = sub.add_parser(
        "scan", parents=[common], help="compile an existing repository (plan first, spend later)"
    )
    scan.add_argument("target", nargs="?", default=".", help="repository root (default: here)")
    scan.add_argument("--dry-run", action="store_true", help="show the plan only (no LLM cost)")
    scan.add_argument("--yes", action="store_true", help="execute the plan")
    scan.add_argument("--background", action="store_true", help="queue a resumable job instead")
    scan.add_argument("--profile", choices=list(PROFILES), default="all")
    scan.add_argument("--max-files", type=int, default=None)
    scan.add_argument("--include", action="append", default=[], metavar="GLOB")
    scan.add_argument("--exclude", action="append", default=[], metavar="GLOB")
    scan.add_argument(
        "--allow-secrets",
        action="store_true",
        help="proceed despite flagged secrets (content is redacted before the LLM)",
    )
    consolidate = sub.add_parser("consolidate", parents=[common], help="merge duplicate concepts")
    consolidate.add_argument("--apply", action="store_true", help="actually merge (default: list)")
    verify = sub.add_parser("verify", parents=[common], help="check a note against its source")
    verify.add_argument("title", nargs="?", default=None)
    verify.add_argument("--apply", action="store_true", help="apply the correction")
    verify.add_argument("--all", action="store_true", help="batch: every note (LLM per note)")
    verify.add_argument(
        "--stale", action="store_true", help="batch: provenance health only (no LLM)"
    )
    verify.add_argument("--source", default=None, help="batch: only notes from this source")
    overview = sub.add_parser("overview", parents=[common], help="show the domain overview")
    overview.add_argument("--rebuild", action="store_true", help="re-induce the domains")
    ask = sub.add_parser("ask", parents=[common], help="ask the brain (cited answer)")
    ask.add_argument("question")
    ask.add_argument(
        "--trace", action="store_true", help="explain the route: domains, candidates, tokens"
    )
    ask.add_argument(
        "--as-of", dest="as_of", default=None, help="answer from the brain as it was at this time"
    )
    search = sub.add_parser("search", parents=[common], help="find relevant notes")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5, help="max results (default 5)")
    for scoped in (overview, ask, search):
        scoped.add_argument(
            "--scope", choices=list(SCOPE_POLICIES), default=None, help="brain scope policy"
        )
        scoped.add_argument(
            "--all-brains",
            dest="all_brains",
            action="store_true",
            help="alias for --scope all (search every registered brain)",
        )
    read = sub.add_parser("read", parents=[common], help="print a note by title")
    read.add_argument("title")
    read.add_argument("--as-of", dest="as_of", default=None, help="version current at this time")
    tl = sub.add_parser("timeline", parents=[common], help="both timelines of a note")
    tl.add_argument("title")
    history = sub.add_parser("history", parents=[common], help="show a note's past versions")
    history.add_argument("title")
    history.add_argument("--as-of", default=None, help="version current at this ISO time")
    recall = sub.add_parser("recall", parents=[common], help="retrieve context for a question")
    recall.add_argument("question")
    recall.add_argument("--limit", type=int, default=5, help="max notes of context (default 5)")
    recall.add_argument(
        "--scope", choices=list(SCOPE_POLICIES), default=None, help="brain scope policy"
    )
    recall.add_argument(
        "--all-brains", dest="all_brains", action="store_true", help="alias for --scope all"
    )
    ev = sub.add_parser("eval", parents=[common], help="measure retrieval quality on a cases file")
    ev.add_argument("--cases", default=None, help='JSON: [{"question","relevant":[titles]}]')
    ev.add_argument("-k", type=int, default=5, help="cutoff for recall@k (default 5)")
    ev.add_argument("--category", default=None, help="run only cases of this category")
    ev.add_argument("--scale", action="store_true", help="latency benchmark at growing sizes")
    ev.add_argument("--sizes", default=None, help="comma-separated note counts for --scale")
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
        return _cmd_panel(resolve_brain(None, None, False))
    if command == "quickstart":
        return _cmd_quickstart()
    if command == "brains":
        return _cmd_brains_group(args)
    if command == "completion":
        return _cmd_completion(args.shell)

    if command == "setup":
        resolved = resolve_init_root(args.root, args.brain, args.use_global)
        return _cmd_setup(resolved.root, args.engine)

    if command == "init":
        resolved = resolve_init_root(args.root, args.brain, args.use_global)
        code = _cmd_init(resolved.root, args.engine, resolved.scope)
        if code == 0 and getattr(args, "scan", False):
            plan = build_plan(Path.cwd(), profile=args.profile)
            print()
            print(format_plan(plan))
            print("\n(no LLM call made; review the plan, then run `talamus scan . --yes`)")
        return code

    root = _resolve_root(
        getattr(args, "root", None),
        getattr(args, "brain", None),
        getattr(args, "use_global", False),
    )
    json_out = bool(getattr(args, "json", False))
    policy = "all" if getattr(args, "all_brains", False) else getattr(args, "scope", None)
    try:
        if command == "where":
            return _cmd_where(resolve_brain(args.root, args.brain, args.use_global), json_out)
        if command == "export":
            return _cmd_export(root, args.file)
        if command == "import":
            return _cmd_import(args.file, root)
        if command == "ontology":
            return _cmd_ontology_group(
                args, root, lambda: llm if llm is not None else _provider_for(root)
            )
        if command == "jobs":
            return _cmd_jobs_group(args, root)
        if command == "review":
            return _cmd_review_group(args, root)
        if command == "demo":
            return _cmd_demo(root)
        if command == "ui":
            return _cmd_ui(root, args.web, args.port)
        if command == "mcp":
            return _cmd_mcp_install(root)
        if command == "hook":
            return _cmd_hook(root)
        if command == "hook-run":
            return _cmd_hook_run(root)
        if command == "status":
            return _cmd_status(root, json_out)
        if command == "doctor":
            return _cmd_doctor(root)
        if command == "reindex":
            return _cmd_reindex(root, json_out)
        if command == "search":
            return _cmd_search(root, args.query, json_out, args.limit, policy)
        if command == "read":
            return _cmd_read(root, args.title, json_out, args.as_of)
        if command == "timeline":
            return _cmd_timeline(root, args.title, json_out)
        if command == "history":
            return _cmd_history(root, args.title, args.as_of, json_out)
        if command == "recall":
            return _cmd_recall(root, args.question, json_out, args.limit, policy)
        if command == "eval":
            if args.scale:
                return _cmd_eval_scale(args.sizes, json_out)
            if not args.cases:
                print("error: pass --cases FILE or --scale", file=sys.stderr)
                return 1
            return _cmd_eval(root, args.cases, args.k, json_out, args.category)
        if command == "neighbors":
            return _cmd_neighbors(root, args.concept, json_out)
        if command == "relations":
            return _cmd_relations(root, args.prune, json_out)
        if command == "scan":
            return _cmd_scan(
                root,
                args.target,
                lambda: llm if llm is not None else _provider_for(root),
                args,
            )
        provider = llm if llm is not None else _provider_for(root)
        if command == "ingest":
            return _cmd_ingest(root, args.target, provider, json_out)
        if command == "consolidate":
            return _cmd_consolidate(root, args.apply, provider, json_out)
        if command == "verify":
            if args.all or args.stale or args.source:
                return _cmd_verify_batch(root, provider, args.stale, args.source, json_out)
            if not args.title:
                print("error: pass a note title, or --all / --stale / --source", file=sys.stderr)
                return 1
            return _cmd_verify(root, args.title, args.apply, provider, json_out)
        if command == "overview":
            return _cmd_overview(root, provider, json_out, args.rebuild, policy)
        if command == "ask":
            return _cmd_ask(root, args.question, provider, json_out, policy, args.trace, args.as_of)
        if command == "remember":
            return _cmd_remember(root, args.transcript, args.diff, provider, json_out)
    except TalamusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    raise ValueError(f"unknown command {command}")


if __name__ == "__main__":
    raise SystemExit(main())
