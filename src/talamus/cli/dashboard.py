from __future__ import annotations

import sys
from pathlib import Path

from talamus.cli._common import (
    _print_json,
)
from talamus.jobs import JobStore
from talamus.ontology_lab import (
    schema_status,
)
from talamus.paths import TalamusPaths
from talamus.registry import (
    central_brain,
)
from talamus.review import ReviewQueue
from talamus.scope import (
    ResolvedBrain,
)


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
        suggestions.append("talamus ingest <file>   or   talamus scan . --dry-run")
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
        print("Status     no brain here (run talamus init to create one)")
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


def _cmd_ui(root: Path, web: bool = False, port: int = 8760) -> int:
    """Launch the web workbench (React SPA + FastAPI bridge over services/).

    Native window via pywebview by default; --web opens the browser instead.
    This replaced the legacy Flet app at parity (P7)."""
    try:
        from talamus.webapi.__main__ import main as run_workbench
    except ImportError:
        print("UI needs the 'ui' extra: pip install talamus[ui]", file=sys.stderr)
        return 1
    args = ["--root", str(root), "--port", str(port)]
    if web:
        args.append("--web")
    run_workbench(args)
    return 0


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
