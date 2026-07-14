"""The temporal-freshness benchmark: does "today" always get the NEW truth?

The scenario the maintainer defined: procedure v1 (2025) and procedure v2
(2026) both live in the brain as separate notes. A question asked today must
be answered from v2 — ideally saying the information changed — and must never
present v1 as current. Half the pairs are LINKED with the bitemporal
supersedes handover (the freshness pass should exclude v1 from context
mechanically); the other half are UNLINKED and rely only on the dated-context
answer contract. The split is the point: it measures the guarantee separately
from the heuristic.

Brain construction is deterministic and free (notes are written directly, no
extraction LLM); only the answers spend LLM calls (~1 per question). Scoring
is deterministic marker containment — no judge needed.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from talamus.ask import answer_question
from talamus.config import TalamusConfig, save_config
from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.routing import EngineRouter, Router
from talamus.store import load_notes, rebuild_indexes, render_note_markdown, write_note_json
from talamus.temporal import record_supersedes

V1_STAMP = "2025-06-01T09:00:00+00:00"
V2_STAMP = "2026-07-01T09:00:00+00:00"
CHANGE_WORDS = ("supersed", "replac", "chang", "no longer", "not current", "was valid", "until")


@dataclasses.dataclass(frozen=True)
class Pair:
    pid: str
    topic: str  # vocabulary shared by both versions (drives retrieval)
    question: str
    v1_summary: str
    v1_marker: str
    v2_summary: str
    v2_marker: str
    linked: bool  # True = the supersedes handover is recorded


PAIRS: list[Pair] = [
    Pair(
        "expense",
        "expense reimbursement procedure",
        "What is the current expense reimbursement procedure?",
        "Expenses are reimbursed by mailing the paper form 33-B within 30 days.",
        "paper form 33-b",
        "Expenses are reimbursed by uploading the receipt to the Concur portal within 15 days.",
        "concur portal",
        True,
    ),
    Pair(
        "password",
        "password policy rotation",
        "What is our password policy?",
        "Passwords rotate every 90 days and require 8 characters.",
        "every 90 days",
        "Passwords never expire; passphrases of 16+ characters with MFA are required.",
        "never expire",
        True,
    ),
    Pair(
        "deploy",
        "production deploy process release",
        "How do we deploy to production?",
        "Deploys go through the Jenkins freeze window every Thursday night.",
        "jenkins freeze",
        "Deploys ship continuously through the ArgoCD pipeline after canary checks.",
        "argocd",
        True,
    ),
    Pair(
        "vacation",
        "vacation leave request approval",
        "How do I request vacation days?",
        "Vacation requests are emailed to HR with the yellow PTO sheet.",
        "yellow pto sheet",
        "Vacation is requested in the Workday self-service portal with automatic manager approval.",
        "workday",
        True,
    ),
    Pair(
        "apiver",
        "public api version clients",
        "Which API version should clients use?",
        "Clients must call the SOAP v2 endpoint at /api/v2.",
        "soap v2",
        "Clients must call the GraphQL v4 gateway at /graphql.",
        "graphql v4",
        True,
    ),
    Pair(
        "meeting",
        "team meeting cadence standup",
        "What is the team meeting cadence?",
        "The team meets daily at 9:00 for a 30-minute standup.",
        "daily at 9:00",
        "The team meets twice a week, Tuesday and Thursday, async otherwise.",
        "twice a week",
        True,
    ),
    Pair(
        "pricing",
        "product pricing plan tiers",
        "What is the current pricing?",
        "The product costs 49 euro per seat per month, annual only.",
        "49 euro",
        "The product costs 29 euro per seat per month with a free tier.",
        "29 euro",
        False,
    ),
    Pair(
        "sla",
        "support sla response time",
        "What is our support SLA?",
        "Support answers within 48 hours on business days.",
        "48 hours",
        "Support answers within 4 hours, 24/7, for all paid plans.",
        "4 hours",
        False,
    ),
    Pair(
        "dbengine",
        "database engine storage",
        "Which database engine do we use?",
        "The service stores data in MySQL 5.7 on self-managed VMs.",
        "mysql 5.7",
        "The service stores data in PostgreSQL 16 on managed Cloud SQL.",
        "postgresql 16",
        False,
    ),
    Pair(
        "style",
        "code style guide formatting",
        "What is our code style rule for line length?",
        "The style guide caps lines at 79 characters, tabs forbidden.",
        "79 characters",
        "The style guide caps lines at 120 characters, enforced by the formatter.",
        "120 characters",
        False,
    ),
    Pair(
        "backup",
        "backup schedule retention",
        "What is the backup schedule?",
        "Backups run weekly on Sunday with 30-day retention.",
        "weekly on sunday",
        "Backups run hourly with point-in-time recovery and 1-year retention.",
        "hourly",
        False,
    ),
    Pair(
        "office",
        "office address headquarters",
        "What is the office address?",
        "The office is at Via Roma 12, third floor.",
        "via roma 12",
        "The office is at Corso Milano 88, ground floor.",
        "corso milano 88",
        False,
    ),
]


def _note(pair: Pair, version: int) -> CanonicalNote:
    summary = pair.v1_summary if version == 1 else pair.v2_summary
    year = "2025" if version == 1 else "2026"
    return CanonicalNote(
        note_id=f"{pair.pid}-{year}",
        title=f"{pair.topic.title()} ({year})",
        aliases=[],
        folder="",
        tags=["procedure"],
        summary=summary,
        retrieval_text=f"{pair.topic} {pair.question.lower()}",
        body_sections={"core_idea": summary},
        proposed_links=[],
        relations=[],
        sources=[
            SourceRef(
                raw_path=f"raw/{pair.pid}-{year}.md",
                normalized_path=f"normalized/{pair.pid}-{year}#1",
                locator="",
                source_hash="sha256:bench",
                supported_claims=[summary],
            )
        ],
        confidence=0.9,
    )


def _backdate(paths: TalamusPaths, note_id: str, stamp: str) -> None:
    """Benchmark-only: set the machine record's timestamps so the dated-context
    contract has real dates to prefer (the store stamps 'now' on write)."""
    record = paths.notes_cache / f"{note_id}.json"
    data = json.loads(record.read_text(encoding="utf-8"))
    data["created_at"] = stamp
    data["updated_at"] = stamp
    record.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_temporal_brain(root: Path, engine: str = "claude-cli") -> TalamusPaths:
    paths = TalamusPaths(root)
    paths.ensure_directories()
    save_config(
        paths.config_path,
        dataclasses.replace(TalamusConfig.default(), llm_provider=engine),
    )
    for pair in PAIRS:
        for version in (1, 2):
            write_note_json(paths, _note(pair, version))
    registry = NoteRegistry.from_notes(load_notes(paths))
    for note in load_notes(paths):
        render_note_markdown(paths, note, registry)
    rebuild_indexes(paths)
    for pair in PAIRS:
        if pair.linked:
            record_supersedes(paths, f"{pair.topic.title()} (2025)", f"{pair.topic.title()} (2026)")
    for pair in PAIRS:
        _backdate(paths, f"{pair.pid}-2025", V1_STAMP)
        _backdate(paths, f"{pair.pid}-2026", V2_STAMP)
    rebuild_indexes(paths)
    return paths


def _score(pair: Pair, answer: str, trace: dict) -> dict:
    low = answer.lower()
    current_hit = pair.v2_marker in low
    stale = pair.v1_marker in low and not current_hit
    change_noted = current_hit and (
        pair.v1_marker in low or any(word in low for word in CHANGE_WORDS)
    )
    return {
        "pid": pair.pid,
        "linked": pair.linked,
        "current_hit": current_hit,
        "stale": stale,
        "change_noted": change_noted,
        "old_excluded_from_context": bool(trace.get("superseded_dropped")),
    }


def _rate(rows: list[dict], key: str) -> float:
    return round(sum(1 for r in rows if r[key]) / len(rows), 3) if rows else 0.0


def run_temporal_eval(
    engine: str = "claude-cli",
    router: Router | None = None,
    out_dir: Path | None = None,
    keep_dir: Path | None = None,
) -> dict:
    """Build the two-version brain, ask every question "today", score
    deterministically. ``router`` overrides the engine (tests use a fake)."""
    workdir = keep_dir or Path(tempfile.mkdtemp(prefix="talamus-temporal-"))
    paths = build_temporal_brain(workdir, engine=engine)
    active_router = router or EngineRouter(
        dataclasses.replace(TalamusConfig.default(), llm_provider=engine)
    )
    rows: list[dict] = []
    for pair in PAIRS:
        trace: dict = {}
        answer = answer_question(paths, pair.question, active_router, trace=trace)
        rows.append(_score(pair, answer, trace) | {"answer": answer})
    linked = [r for r in rows if r["linked"]]
    unlinked = [r for r in rows if not r["linked"]]
    result = {
        "benchmark": "temporal-freshness",
        "date": time.strftime("%Y-%m-%d"),
        "engine": engine if router is None else "injected-router",
        "pairs": len(PAIRS),
        "overall": {
            "current_hit": _rate(rows, "current_hit"),
            "stale": _rate(rows, "stale"),
            "change_noted": _rate(rows, "change_noted"),
        },
        "linked_supersedes": {
            "current_hit": _rate(linked, "current_hit"),
            "stale": _rate(linked, "stale"),
            "change_noted": _rate(linked, "change_noted"),
            "old_excluded_from_context": _rate(linked, "old_excluded_from_context"),
        },
        "unlinked_dated_only": {
            "current_hit": _rate(unlinked, "current_hit"),
            "stale": _rate(unlinked, "stale"),
            "change_noted": _rate(unlinked, "change_noted"),
        },
        "rows": rows,
    }
    if out_dir is not None:
        _write_artifacts(result, out_dir)
    return result


def _write_artifacts(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = result["date"]
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=15
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        commit = "unknown"
    (out_dir / f"{stamp}-temporal.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    o = result["overall"]
    li = result["linked_supersedes"]
    un = result["unlinked_dated_only"]
    report = (
        f"# Temporal freshness — {stamp}\n\n"
        f"Command: `python benchmarks/temporal_eval.py --engine {result['engine']} --yes`\n"
        f"(commit {commit}; {result['pairs']} v1/v2 pairs, half linked with the\n"
        f"supersedes handover, half unlinked — dated context only)\n\n"
        f"| slice | current answer uses v2 | stale (v1 as current) | change noted |\n"
        f"|---|---:|---:|---:|\n"
        f"| overall | {o['current_hit']} | {o['stale']} | {o['change_noted']} |\n"
        f"| linked (supersedes) | {li['current_hit']} | {li['stale']} | {li['change_noted']} |\n"
        f"| unlinked (dates only) | {un['current_hit']} | {un['stale']} "
        f"| {un['change_noted']} |\n\n"
        f"Old note mechanically excluded from context on linked pairs: "
        f"{li['old_excluded_from_context']}.\n"
        f"Scoring is deterministic marker containment; no LLM judge involved.\n"
    )
    (out_dir / f"{stamp}-temporal.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Temporal-freshness benchmark")
    parser.add_argument("--engine", default="claude-cli")
    parser.add_argument("--out", default="benchmarks/results")
    parser.add_argument("--yes", action="store_true", help="confirm the LLM spend")
    args = parser.parse_args()
    calls = len(PAIRS)
    if not args.yes:
        print(f"This run makes ~{calls} answer calls on '{args.engine}'. Re-run with --yes.")
        return 2
    result = run_temporal_eval(engine=args.engine, out_dir=Path(args.out))
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
