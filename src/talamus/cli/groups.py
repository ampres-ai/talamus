from __future__ import annotations

import argparse
import sys
from pathlib import Path

from talamus.cli._common import (
    JOB_RUNNERS,
    _print_json,
)
from talamus.federation import build_federated_index, federation_status
from talamus.jobs import JobStore
from talamus.ontology_lab import (
    induce_candidates,
    infer_property_candidates,
    ontology_eval,
    stability,
)
from talamus.paths import TalamusPaths
from talamus.registry import (
    load_registry,
    talamus_home,
)
from talamus.routing import Router
from talamus.scope import (
    promote_note,
)
from talamus.services.brains import (
    register_existing_brain,
    rename_registered_brain,
    select_registered_brain,
    set_registered_brain_flags,
    unregister_registered_brain,
)
from talamus.services.jobs import cancel_job, get_job, list_jobs, read_job_log
from talamus.services.ontology import (
    OntologyPropertyCandidate,
    apply_ontology_candidate,
    deprecate_ontology_type,
    export_ontology_schema,
    get_ontology_history,
    get_ontology_status,
    list_ontology_candidates,
    reject_ontology_candidate,
)
from talamus.services.review import (
    apply_review_item,
    get_review_item,
    list_review_items,
    reject_review_item,
)


def _cmd_ontology_group(args: argparse.Namespace, root: Path, router: Router) -> int:
    paths = TalamusPaths(root)
    cmd = getattr(args, "ontology_cmd", None) or "status"
    json_out = bool(getattr(args, "json", False))
    if cmd == "status":
        status_result = get_ontology_status(root)
        if not status_result.success or status_result.data is None:
            print(status_result.message, file=sys.stderr)
            return 1
        status = status_result.data.to_dict()
        if json_out:
            _print_json(status)
            return 0
        print(f"schema: {status['schema_id']} (v{status['version']})")
        for state, count in sorted(status["types"].items()):
            print(f"  {state}: {count}")
        cov = status["coverage"]
        print(
            f"coverage: {cov['non_related']}/{cov['edges']} typed edges "
            f"({cov['non_related_share']:.0%})"
        )
        return 0
    if cmd == "induce":
        created = induce_candidates(paths, router, min_support=args.min_support)
        if json_out:
            _print_json([c.to_dict() for c in created])
            return 0
        if not created:
            print("no new candidate (surfaces already explained or insufficient support)")
            return 0
        print(f"{len(created)} candidate types induced:")
        for candidate in created:
            print(f"  - {candidate.id}  support={candidate.support}  «{candidate.definition}»")
        print("review with `talamus ontology review`, promote with `talamus ontology apply ID`")
        return 0
    if cmd == "infer":
        proposed = infer_property_candidates(paths)
        if json_out:
            _print_json([candidate.to_dict() for candidate in proposed])
            return 0
        if not proposed:
            print("no new property candidate (insufficient structural witnesses)")
            return 0
        print(f"{len(proposed)} property candidates inferred:")
        for prop in proposed:
            value = f" -> {prop.value}" if prop.value else ""
            print(f"  - {prop.id}  {prop.property} {prop.type_id}{value}  support={prop.support}")
        print("review with `talamus ontology review`, promote with `talamus ontology apply ID`")
        return 0
    if cmd == "review":
        pending_result = list_ontology_candidates(root)
        if not pending_result.success or pending_result.data is None:
            print(pending_result.message, file=sys.stderr)
            return 1
        pending = pending_result.data
        if json_out:
            _print_json([rel_type.to_dict() for rel_type in pending])
            return 0
        if not pending:
            print("no candidates pending")
        for rel_type in pending:
            if isinstance(rel_type, OntologyPropertyCandidate):
                value = f" -> {rel_type.value}" if rel_type.value else ""
                print(
                    f"- {rel_type.id}  [property] {rel_type.property} "
                    f"{rel_type.type_id}{value}  support={rel_type.support} "
                    f"note={rel_type.distinct_notes}"
                )
            else:
                print(f"- {rel_type.id}  support={rel_type.support} note={rel_type.distinct_notes}")
                if rel_type.definition:
                    print(f"    {rel_type.definition}")
            for example in rel_type.examples[:2]:
                print(f"    e.g. {example}")
        return 0
    if cmd == "apply":
        decision_result = apply_ontology_candidate(root, args.type_id, force=args.force)
        if decision_result.success:
            print(decision_result.message)
            return 0
        print(f"error: {decision_result.message}", file=sys.stderr)
        return 1
    if cmd == "reject":
        decision_result = reject_ontology_candidate(
            root,
            args.type_id,
            reason=getattr(args, "reason", "") or "",
        )
        if decision_result.success:
            print(decision_result.message)
            return 0
        print(f"error: {decision_result.message}", file=sys.stderr)
        return 1
    if cmd == "deprecate":
        decision_result = deprecate_ontology_type(
            root,
            args.type_id,
            reason=getattr(args, "reason", "") or "",
        )
        if decision_result.success:
            print(decision_result.message)
            return 0
        print(f"error: {decision_result.message}", file=sys.stderr)
        return 1
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
            f"emergent : recall@{report['k']} {report['emergent']['recall_at_k']}"
            f"  MRR {report['emergent']['mrr']}"
        )
        print(f"lift     : recall {report['lift']['recall_at_k']:+}  MRR {report['lift']['mrr']:+}")
        cov = report["coverage"]
        print(f"coverage : {cov['non_related_share']:.0%} typed edges")
        return 0
    if cmd == "stability":
        stability_result = stability(paths, runs=args.runs)
        _print_json(stability_result) if json_out else print(
            f"stability (Jaccard, {stability_result['runs']} run): {stability_result['jaccard']}"
        )
        return 0
    if cmd == "history":
        history_result = get_ontology_history(root)
        if not history_result.success or history_result.data is None:
            print(history_result.message, file=sys.stderr)
            return 1
        events = history_result.data.events
        if json_out:
            _print_json(events)
            return 0
        if not events:
            print("no schema events")
        for event in events:
            print(f"- {event.get('at', '?')}  {event.get('event', '?')}  {event.get('type', '')}")
        return 0
    if cmd == "export":
        export_result = export_ontology_schema(root)
        if not export_result.success or export_result.data is None:
            print(export_result.message, file=sys.stderr)
            return 1
        _print_json(export_result.data.schema)
        return 0
    raise ValueError(f"unknown ontology command {cmd}")


def _cmd_jobs_group(args: argparse.Namespace, root: Path) -> int:
    cmd = getattr(args, "jobs_cmd", None) or "list"
    json_out = bool(getattr(args, "json", False))
    if cmd == "list":
        list_result = list_jobs(root)
        if not list_result.success or list_result.data is None:
            print(f"error: {list_result.message}", file=sys.stderr)
            return 1
        records = list_result.data
        if json_out:
            _print_json([record.to_dict() for record in records])
            return 0
        if not records:
            print("no jobs")
        for record in records:
            progress = record.progress or {}
            done = progress.get("done", "-")
            total = progress.get("total", "-")
            print(f"- {record.job_id}  {record.state}  {done}/{total}")
        return 0
    job_result = get_job(root, args.job_id)
    if not job_result.success or job_result.data is None:
        print(job_result.message, file=sys.stderr)
        return 1
    job = job_result.data
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
        log_result = read_job_log(root, args.job_id)
        if not log_result.success or log_result.data is None:
            print(log_result.message, file=sys.stderr)
            return 1
        log = log_result.data.log
        print(log if log else "no log")
        return 0
    if cmd == "cancel":
        cancel_result = cancel_job(root, args.job_id)
        if cancel_result.success:
            print(f"cancelled {args.job_id}")
            return 0
        print(cancel_result.message, file=sys.stderr)
        return 1
    if cmd == "resume":
        resume_record = JobStore(TalamusPaths(root)).load(args.job_id)
        if resume_record is None:
            print(f"no job '{args.job_id}'", file=sys.stderr)
            return 1
        runner = JOB_RUNNERS.get(resume_record.kind)
        if runner is None:
            print(
                f"error: no runner available for job kind '{resume_record.kind}'\n"
                f"cause: this kind is resumed by the feature that created it\n"
                f"fix: re-run the original command",
                file=sys.stderr,
            )
            return 1
        return runner(root, resume_record)
    raise ValueError(f"unknown jobs command {cmd}")


def _cmd_review_group(args: argparse.Namespace, root: Path) -> int:
    cmd = getattr(args, "review_cmd", None) or "list"
    json_out = bool(getattr(args, "json", False))
    if cmd == "list":
        status = None if getattr(args, "all", False) else "pending"
        list_result = list_review_items(root, status=status)
        if not list_result.success or list_result.data is None:
            print(f"error: {list_result.message}", file=sys.stderr)
            return 1
        items = list_result.data
        if json_out:
            _print_json([item.to_dict() for item in items])
            return 0
        if not items:
            print("review queue empty")
        for item in items:
            print(f"- {item.item_id}  [{item.kind}]  {item.status}  {item.title}")
        return 0
    entry_result = get_review_item(root, args.item_id)
    if not entry_result.success or entry_result.data is None:
        print(entry_result.message, file=sys.stderr)
        return 1
    entry = entry_result.data
    if cmd == "show":
        if json_out:
            _print_json(entry.to_dict())
            return 0
        for key, value in entry.to_dict().items():
            print(f"{key}: {value}")
        return 0
    if cmd == "apply":
        applied = apply_review_item(root, args.item_id)
        if not applied.success or applied.data is None:
            print(applied.message, file=sys.stderr)
            return 1
        print(f"applied {applied.data.item_id} ({applied.data.kind})")
        return 0
    if cmd == "reject":
        rejected = reject_review_item(root, args.item_id, getattr(args, "reason", "") or "")
        if not rejected.success or rejected.data is None:
            print(rejected.message, file=sys.stderr)
            return 1
        print(f"rejected {rejected.data.item_id} (kept in the log)")
        return 0
    raise ValueError(f"unknown review command {cmd}")


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
            print(f"- {name}  (not registered — `talamus brains register {home / name}`)")
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
    print(f"federated index built: {report['rows']} notes from {len(report['brains'])} brains")
    for entry in report["brains"]:
        skipped = f" ({entry['skipped']})" if "skipped" in entry else ""
        print(f"  - {entry['brain']}: {entry['notes']} notes{skipped}")
    for warning in report["warnings"]:
        print(f"  ! {warning}")
    return 0


def _cmd_brains_group(args: argparse.Namespace) -> int:
    cmd = getattr(args, "brains_cmd", None) or "list"
    json_out = bool(getattr(args, "json", False))
    if cmd == "list":
        return _cmd_brains_list(json_out)
    if cmd == "use":
        select_result = select_registered_brain(args.name)
        if select_result.success:
            print(f"selected brain: {args.name}")
            return 0
        print(f"{select_result.message} (see `talamus brains list`)", file=sys.stderr)
        return 1
    if cmd == "info":
        return _cmd_brains_info(args.name, json_out)
    if cmd == "rename":
        rename_result = rename_registered_brain(args.old, args.new)
        if not rename_result.success:
            print(f"error: {rename_result.message}", file=sys.stderr)
            return 1
        print(f"renamed: {args.old} -> {args.new}")
        return 0
    if cmd == "delete":
        delete_result = unregister_registered_brain(args.name)
        if delete_result.success:
            print(f"unregistered '{args.name}' (files on disk are preserved)")
            return 0
        print(delete_result.message, file=sys.stderr)
        return 1
    if cmd == "register":
        register_result = register_existing_brain(Path(args.path), args.name, args.type)
        if not register_result.success or register_result.data is None:
            print(f"error: {register_result.message}", file=sys.stderr)
            return 1
        info = register_result.data
        print(f"registered '{info.name}' ({info.type}) at {info.path}")
        return 0
    if cmd == "set":
        federated = getattr(args, "federated", None)
        sensitive = getattr(args, "sensitive", None)
        if federated is None and sensitive is None:
            print("nothing to set (pass --federated and/or --sensitive)", file=sys.stderr)
            return 1
        flags_result = set_registered_brain_flags(
            args.name,
            federated=None if federated is None else federated == "true",
            sensitive=None if sensitive is None else sensitive == "true",
        )
        if not flags_result.success:
            print(flags_result.message, file=sys.stderr)
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
