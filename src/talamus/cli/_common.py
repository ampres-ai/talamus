from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from talamus.config import load_or_default
from talamus.jobs import JobRecord
from talamus.paths import TalamusPaths
from talamus.routing import EngineRouter
from talamus.scope import (
    resolve_brain,
)
from talamus.services.engines import choose_default_engine


def _detect_engine() -> str:
    """Pick an LLM engine that is actually installed; fall back to claude-cli."""
    return choose_default_engine()


def _resolve_root(root: str | None, brain: str | None, use_global: bool) -> Path:
    """Which brain to use (see talamus.scope.resolve_brain for the full order)."""
    return resolve_brain(root, brain, use_global).root


def _router_for(root: Path) -> EngineRouter:
    """Build the per-task engine router for a brain (reads its config each call)."""
    return EngineRouter(load_or_default(TalamusPaths(root).config_path))


def _ensure_utf8_output() -> None:
    """Force UTF-8 output where possible (the Windows console otherwise mangles accents)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


_ALL_COMMANDS = (
    "setup init demo ui status doctor curator reindex ingest scan consolidate enrich verify "
    "supersede watch ask overview search read "
    "history timeline recall neighbors relations remember eval ontology jobs review quickstart "
    "brains where export import import-vault completion mcp hook hook-run"
)

# Runners that can resume a persisted job, keyed by kind (scan registers below).
JOB_RUNNERS: dict[str, Callable[[Path, JobRecord], int]] = {}
