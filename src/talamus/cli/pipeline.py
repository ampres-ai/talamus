from __future__ import annotations

import argparse
import sys
from pathlib import Path

from talamus.cli._common import (
    JOB_RUNNERS,
    _print_json,
    _router_for,
)
from talamus.domains import build_overview, load_overview
from talamus.jobs import JobRecord
from talamus.paths import TalamusPaths
from talamus.registry import (
    load_registry,
)
from talamus.routing import Router
from talamus.scan import (
    execute_plan,
    format_plan,
    plan_from_record,
)
from talamus.services.consolidation import apply_consolidation_groups, list_consolidation_groups
from talamus.services.enrich import EnrichPreview, EnrichRunResult, run_enrich
from talamus.services.ingestion import IngestPreview, IngestRunResult, run_ingest
from talamus.services.scan import ScanActionResult, ScanPreview, preview_scan, run_scan
from talamus.services.verification import (
    VerificationBatchResult,
    VerificationNoteResult,
    apply_note_correction,
    run_verification_batch,
    verify_single_note,
)


def _cmd_scan(
    root: Path,
    target: str,
    router: Router,
    args: argparse.Namespace,
) -> int:
    json_out = bool(getattr(args, "json", False))
    if args.dry_run or not (args.yes or args.background):
        preview_result = preview_scan(
            root,
            target,
            profile=args.profile,
            include=args.include or None,
            exclude=args.exclude or None,
            max_files=args.max_files,
        )
        if not preview_result.success or not isinstance(preview_result.data, ScanPreview):
            print(preview_result.message, file=sys.stderr)
            return 1
        plan = preview_result.data.plan
        if json_out:
            _print_json(plan.to_dict())
        else:
            print(format_plan(plan))
            if not args.dry_run:
                print("\n(dry-run shown; pass --yes to execute or --background to queue a job)")
        return 0
    service_result = run_scan(
        root,
        target,
        router,
        profile=args.profile,
        include=args.include or None,
        exclude=args.exclude or None,
        max_files=args.max_files,
        confirmed=args.yes,
        background=args.background,
        allow_secrets=args.allow_secrets,
    )
    if service_result.code == "scan_secrets_blocked" and isinstance(
        service_result.data, ScanPreview
    ):
        flagged = service_result.data.secret_files
        print(
            "error: likely secrets detected; scan stopped before any LLM call\n"
            f"cause: {len(flagged)} file(s) flagged: {', '.join(flagged[:5])}\n"
            "fix: review the files, then re-run with --allow-secrets "
            "(content is redacted) or use a local provider",
            file=sys.stderr,
        )
        return 1
    if service_result.code == "scan_nothing_to_scan":
        print("nothing to scan (no supported files in plan)")
        return 0
    if service_result.code == "scan_queued" and isinstance(service_result.data, ScanActionResult):
        result = service_result.data
        print(f"queued scan job {result.job_id} ({result.files} files)")
        print(f"run it with:  talamus jobs resume {result.job_id}")
        return 0
    if not service_result.success or not isinstance(service_result.data, ScanActionResult):
        print(service_result.message, file=sys.stderr)
        return 1
    report = service_result.data.raw
    if json_out:
        _print_json(report)
        return 0
    print(
        f"scan {report['state']}: {report['notes_written']} notes from "
        f"{report['files']} files (job {report['job_id']})"
    )
    for failure in report["failed"]:
        print(f"  ! {failure['path']}: {failure['error']}")
    return 0


def _run_scan_job(root: Path, record: JobRecord) -> int:
    """Resume runner registered in JOB_RUNNERS for `talamus jobs resume`."""
    paths = TalamusPaths(root)
    plan = plan_from_record(record)
    report = execute_plan(paths, plan, _router_for(root), job_record=record)
    print(
        f"scan {report['state']}: {report['notes_written']} notes from "
        f"{report['files']} files (job {report['job_id']})"
    )
    return 0


JOB_RUNNERS["scan"] = _run_scan_job


def _run_ingest_job(root: Path, record: JobRecord) -> int:
    """Resume a chunked big-document ingest (talamus jobs resume)."""
    from talamus.ingest import ingest_large

    file_path = Path(str(record.payload.get("file", "")))
    if not file_path.is_file():
        print(f"error: source file missing: {file_path}", file=sys.stderr)
        return 1
    report = ingest_large(TalamusPaths(root), file_path, _router_for(root), job_record=record)
    print(
        f"ingest {report['state']}: {report['notes_written']} notes from "
        f"{report['chunks']} chunks (job {report['job_id']})"
    )
    return 0


JOB_RUNNERS["ingest"] = _run_ingest_job


def _cmd_ingest(root: Path, target: str, router: Router, json_out: bool, yes: bool = False) -> int:
    service_result = run_ingest(root, target, router, confirmed=yes)
    if service_result.code == "ingest_confirmation_required" and isinstance(
        service_result.data, IngestPreview
    ):
        estimate = service_result.data
        print(f"Large document: {estimate.source}")
        print(
            f"  {estimate.chars:,} characters -> {estimate.chunks} chunks = "
            f"{estimate.est_llm_calls} LLM calls "
            f"(~{estimate.est_input_tokens:,} input tokens)"
        )
        print("  The work runs as a resumable job (talamus jobs).")
        print(f'  Confirm with:  talamus ingest "{target}" --yes')
        return 0
    if not service_result.success or not isinstance(service_result.data, IngestRunResult):
        print(service_result.message, file=sys.stderr)
        return 1
    result = service_result.data.raw
    if json_out:
        _print_json(result)
    elif "files" in result:
        print(
            f"ingested {result['notes_written']} notes from {result['files']} files "
            f"({result['skipped']} unchanged skipped)"
        )
        for failure in result.get("failed", []):
            print(f"  ! skipped {failure['file']}: {failure['error']}")
    else:
        suffix = ""
        if "chunks" in result:
            suffix = f" ({result['chunks']} chunks, job {result.get('job_id', '?')})"
        print(f"ingested {result['notes_written']} notes from {result['source']}{suffix}")
        for failure in result.get("failed", []):
            print(f"  ! chunk {failure['chunk']}: {failure['error']}")
    _print_supersedes(result)
    return 0


def _cmd_import_vault(root: Path, directory: str, json_out: bool) -> int:
    """Import a Markdown/Obsidian vault 1:1 — no LLM, wikilinks preserved (P9)."""
    from talamus.services.importer import import_markdown_vault

    result = import_markdown_vault(root, directory)
    if not result.success or result.data is None:
        print(result.message, file=sys.stderr)
        return 1
    if json_out:
        _print_json(result.data.to_dict())
        return 0
    data = result.data
    print(
        f"imported {data.notes_written} notes from {data.vault} ({data.skipped} unchanged skipped)"
    )
    for rel in data.duplicates:
        print(f"  ! duplicate title, kept the first: {rel}")
    for failure in data.failed:
        print(f"  ! failed {failure['file']}: {failure['error']}")
    if data.notes_written:
        print('next: talamus ask "..." — your imported notes are already searchable')
    return 0


def _cmd_consolidate(root: Path, do_apply: bool, router: Router, json_out: bool) -> int:
    if do_apply:
        apply_result = apply_consolidation_groups(root, router)
        if not apply_result.success or apply_result.data is None:
            print(apply_result.message, file=sys.stderr)
            return 1
        merged = apply_result.data.merged
        if json_out:
            _print_json({"merged": merged})
        else:
            print(f"consolidate: merged {merged} note(s)")
        return 0
    list_result = list_consolidation_groups(root, router)
    if not list_result.success or list_result.data is None:
        print(list_result.message, file=sys.stderr)
        return 1
    groups = [group.to_dict() for group in list_result.data.groups]
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


def _cmd_enrich(root: Path, yes: bool, router: Router, json_out: bool) -> int:
    """Symptom enrichment: estimate first, batches only with --yes."""
    service_result = run_enrich(root, router, confirmed=yes)
    if service_result.code == "enrich_nothing_to_do":
        print("all notes already have the symptom vocabulary")
        return 0
    if service_result.code == "enrich_confirmation_required" and isinstance(
        service_result.data, EnrichPreview
    ):
        estimate = service_result.data
        if json_out:
            _print_json(estimate.estimate_dict())
        else:
            print(f"To enrich: {estimate.notes} notes in {estimate.batches} batches")
            print(f"  = {estimate.est_llm_calls} LLM calls")
            print("  Confirm with:  talamus enrich --yes")
        return 0
    if not service_result.success or not isinstance(service_result.data, EnrichRunResult):
        print(service_result.message, file=sys.stderr)
        return 1
    report = service_result.data.raw
    if json_out:
        _print_json(report)
    else:
        print(
            f"enriched {report['enriched']} notes "
            f"({report['failed_batches']} batches failed, {report['skipped']} skipped)"
        )
    return 0


def _cmd_verify_batch(
    root: Path, router: Router, only_stale: bool, source: str | None, json_out: bool
) -> int:
    service_result = run_verification_batch(
        root, router, only_stale=only_stale, source_filter=source
    )
    if not service_result.success or not isinstance(service_result.data, VerificationBatchResult):
        print(service_result.message, file=sys.stderr)
        return 1
    report = service_result.data.raw
    if json_out:
        _print_json(report)
        return 0
    print(
        f"checked {report['checked']} notes: {report['ok']} ok, "
        f"{report['corrections_proposed']} corrections proposed, "
        f"{report['stale']} stale sources, {report['skipped']} skipped"
    )
    if report["corrections_proposed"] or report["stale"]:
        print("review with `talamus review list`")
    return 0


def _print_supersedes(result: dict) -> None:
    detection = result.get("supersedes") or {}
    for entry in detection.get("applied", []):
        print(
            f"supersedes: '{entry['new']}' replaced '{entry['old']}' "
            f"(auto, confidence {entry['confidence']:.2f}) — the old note is kept in history"
        )
    for entry in detection.get("proposed", []):
        print(
            f"supersedes? '{entry['new']}' may replace '{entry['old']}' — "
            "decide with `talamus review`"
        )


def _cmd_watch(
    root: Path, directory: str, router: Router, interval: float, cap: int, once: bool
) -> int:
    """Watch mode: starting the watch IS the consent; the daily cap bounds it."""
    from talamus.watch import watch_folder

    target = Path(directory).resolve()
    if not target.is_dir():
        print(f"not a folder: {target}", file=sys.stderr)
        return 1
    print(f"watching {target} (cap {cap} files/day, every {interval:g}s — Ctrl+C stops)")
    try:
        watch_folder(
            TalamusPaths(root), target, router, interval=interval, daily_cap=cap, once=once
        )
    except KeyboardInterrupt:
        print("watch stopped")
    return 0


def _cmd_supersede(root: Path, old: str, new: str) -> int:
    """The bitemporal handover: nothing is deleted — the old note moves into
    the past (claims closed, typed edge in the graph) and stays reachable
    through history and --as-of."""
    from talamus.temporal import record_supersedes

    try:
        result = record_supersedes(TalamusPaths(root), old, new)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    closed = len(result["claims_closed"])
    print(
        f"'{result['old']}' is now superseded by '{result['new']}'\n"
        f"  the old note is KEPT (history + --as-of still reach it); "
        f"{closed} open claim(s) closed\n"
        f"  default answers now read the successor"
    )
    return 0


def _cmd_verify(root: Path, title: str, do_apply: bool, router: Router, json_out: bool) -> int:
    if do_apply:
        apply_result = apply_note_correction(root, title, router)
        if not apply_result.success or apply_result.data is None:
            print(apply_result.message, file=sys.stderr)
            return 1
        corrected = apply_result.data.corrected
        if json_out:
            _print_json({"corrected": corrected})
        else:
            print(f"verify: {'corrected' if corrected else 'no correction needed for'} '{title}'")
        return 0
    note_result = verify_single_note(root, title, router)
    if not note_result.success or not isinstance(note_result.data, VerificationNoteResult):
        print(note_result.message, file=sys.stderr)
        return 1
    result = note_result.data.raw
    if json_out:
        _print_json(result)
        return 0
    if not result.get("found"):
        print(f"note not found: {title}", file=sys.stderr)
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
    root: Path, router: Router, json_out: bool, rebuild: bool, policy: str | None = None
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
                print(f"## {domain['name']}  ({len(domain.get('members', []))} notes)")
        return 0
    paths = TalamusPaths(root)
    if rebuild or not paths.overview_file.exists():
        from talamus.domains import TREE_THRESHOLD, build_overview_tree

        domains = build_overview(paths, router)
        if len(domains) >= TREE_THRESHOLD:
            areas = build_overview_tree(paths, router)
            if areas and not json_out:
                print(f"(hierarchical map: {len(areas)} macro-areas over {len(domains)} domains)")
    else:
        domains = load_overview(paths)
    if json_out:
        _print_json(domains)
        return 0
    if not domains:
        print("no notes yet (ingest something first)")
        return 0
    for domain in domains:
        print(f"## {domain['name']}  ({len(domain['members'])} notes)")
        if domain.get("description"):
            print(f"   {domain['description']}")
    return 0
