from __future__ import annotations

import argparse
import json
import hashlib
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.fde_brain.classify import classify
from tools.fde_brain.distill_local import DEFAULT_DISTILL_MODEL, distill_normalized_sections
from tools.fde_brain.graphify import mark_graph_stale
from tools.fde_brain.normalize import NormalizedOutput, normalize_source
from tools.fde_brain.paths import WorkspacePaths
from tools.fde_brain.preflight import run_preflight
from tools.fde_brain.registry import RegistryEntry, append_entry
from tools.fde_brain.run_log import FileOutcome, RunLog, write_run_log
from tools.fde_brain.validate_workspace import validate_workspace


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_name(name: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("-", name).strip("-")
    return cleaned or "file"


def _sha256_of(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
            size += len(chunk)
    return f"sha256:{digest.hexdigest()}", size


def _archive(src: Path, paths: WorkspacePaths, category: str, captured_at: datetime) -> Path:
    target_dir = paths.raw_for(category) if category != "unknown" else (paths.raw / "unknown")
    target_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = captured_at.strftime("%Y-%m-%d")
    safe = _sanitize_name(src.name)
    target = target_dir / f"{date_prefix}-{safe}"
    counter = 1
    while target.exists():
        target = target_dir / f"{date_prefix}-{counter}-{safe}"
        counter += 1
    shutil.move(str(src), str(target))
    return target


def _rel(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


_SLUG_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _title_to_filename(title: str) -> str:
    cleaned = _SLUG_SAFE_RE.sub("-", title).strip("-")
    return cleaned or "note"


def _write_distill_review(
    paths: WorkspacePaths,
    run_id: str,
    source_name: str,
    review_items: list[dict],
) -> None:
    if not review_items:
        return
    paths.logs_decisions.mkdir(parents=True, exist_ok=True)
    safe_source = _sanitize_name(source_name)
    out = paths.logs_decisions / f"{run_id}-{safe_source}-distill-review.json"
    payload = {"run_id": run_id, "source": source_name, "review_items": review_items}
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _promote_local(
    normalized: NormalizedOutput,
    paths: WorkspacePaths,
    run_id: str,
    model: str,
) -> list[Path]:
    section_paths = list(normalized.section_paths)
    if not section_paths:
        return []
    result = distill_normalized_sections(
        section_paths=section_paths,
        paths=paths,
        run_id=run_id,
        model=model,
    )
    written: list[Path] = []
    if not result.ok:
        _log("distill", f"FAILED: {result.error}")
        return written
    _write_distill_review(paths, run_id, normalized.package_dir.name if normalized.package_dir else "source", result.review_items)
    paths.fde_brain.mkdir(parents=True, exist_ok=True)
    for note in result.notes:
        filename = f"{_title_to_filename(note.title)}.md"
        promoted_path = paths.fde_brain / filename
        promoted_path.write_text(note.content, encoding="utf-8")
        written.append(promoted_path)
    return written


def _normalized_rel_paths(normalized: NormalizedOutput, root: Path) -> list[str]:
    paths: list[Path] = []
    if normalized.manifest_path:
        paths.append(normalized.manifest_path)
    paths.extend(normalized.section_paths)
    if normalized.quality_report_path:
        paths.append(normalized.quality_report_path)
    if not paths and normalized.output_path:
        paths.append(normalized.output_path)
    return [rel for rel in (_rel(path, root) for path in paths) if rel]


def _log(stage: str, message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [{stage}] {message}", flush=True)


def _process_one(
    src: Path,
    paths: WorkspacePaths,
    run_id: str,
    captured_at: datetime,
    distill_model: str,
) -> FileOutcome:
    pending_name = src.name
    size_mb = src.stat().st_size / 1024 / 1024
    _log("ingest", f"start {pending_name} ({size_mb:.1f} MB)")

    _log("ingest", "computing sha256 …")
    raw_hash, raw_size = _sha256_of(src)
    _log("ingest", f"sha256 done ({raw_hash[:24]}…)")

    category = classify(src)
    _log("ingest", f"classified as {category}")

    raw_path = _archive(src, paths, category, captured_at)
    _log("ingest", f"archived -> {_rel(raw_path, paths.root)}")

    _log("normalize", "starting …")
    normalized: NormalizedOutput = normalize_source(
        raw_path=raw_path,
        category=category,
        raw_hash=raw_hash,
        captured_at=captured_at,
        paths=paths,
    )
    _log("normalize", f"routed_to={normalized.routed_to} parser={normalized.parser}")

    promoted_paths: list[Path] = []
    if normalized.routed_to == "normalized" and normalized.output_path is not None:
        mark_graph_stale(paths.source_graph, f"normalized source changed: {pending_name}")
        _log("distill", f"local section-level branch -> ollama/{distill_model}")
        promoted_paths = _promote_local(normalized, paths, run_id, distill_model)
        _log("distill", f"promoted {len(promoted_paths)} notes")
        if promoted_paths:
            mark_graph_stale(paths.brain_graph, f"FDE Brain notes changed: {pending_name}")

    promoted_rels = [
        rel for rel in (_rel(p, paths.root) for p in promoted_paths) if rel
    ]

    entry = RegistryEntry(
        raw_path=_rel(raw_path, paths.root) or raw_path.as_posix(),
        raw_hash=raw_hash,
        raw_size=raw_size,
        normalized_paths=_normalized_rel_paths(normalized, paths.root),
        category=category,
        parser=normalized.parser,
        captured_at=captured_at.isoformat(),
        ingestion_run=run_id,
        promoted_to=promoted_rels,
    )
    append_entry(paths.registry_path, entry)

    return FileOutcome(
        pending_name=pending_name,
        raw_path=_rel(raw_path, paths.root),
        normalized_path=_rel(normalized.output_path, paths.root),
        routed_to=normalized.routed_to,
        category=category,
        promoted_to=promoted_rels,
        error=normalized.error,
    )


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )


def _write_pre_ingest_checkpoint(paths: WorkspacePaths, run_id: str, started_at: str) -> Path:
    paths.logs_decisions.mkdir(parents=True, exist_ok=True)
    status = _git(paths.root, ["status", "--short"]).stdout.splitlines()
    payload = {
        "run_id": run_id,
        "checkpointed_at": started_at,
        "purpose": "pre-ingest workspace checkpoint",
        "git_status_short": status,
    }
    safe = started_at.replace(":", "").split("+")[0].split(".")[0]
    out = paths.logs_decisions / f"{safe}-{run_id}-pre-ingest-checkpoint.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _commit_changes(root: Path, message: str) -> str | None:
    _git(root, ["add", "AI Space", "FDE Brain"])
    diff = _git(root, ["diff", "--cached", "--quiet"])
    if diff.returncode == 0:
        return None
    result = _git(root, ["commit", "-m", message])
    if result.returncode != 0:
        return None
    rev = _git(root, ["rev-parse", "HEAD"])
    return rev.stdout.strip() or None


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the FDE Brain ingestion pipeline.")
    parser.add_argument("--root", default=".", help="Workspace root.")
    parser.add_argument("--no-commit", action="store_true", help="Skip the final git commit.")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not write logs or commit.")
    parser.add_argument("--distill-model", default=DEFAULT_DISTILL_MODEL, help="Ollama model for local section distillation.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    paths = WorkspacePaths(root)

    issues = validate_workspace(root)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    preflight = run_preflight(distill_model=args.distill_model)
    if not all(r.ok for r in preflight):
        for result in preflight:
            print(result.status_text(), file=sys.stderr)
        return 1

    captured_at = datetime.now(timezone.utc)
    log = RunLog(run_id=_short_uuid(), started_at=captured_at.isoformat())

    pending_files = sorted(
        p for p in paths.pending.iterdir()
        if p.is_file() and p.name != ".gitkeep"
    )

    if args.dry_run:
        for src in pending_files:
            print(f"[dry-run] {src.name} -> would classify/archive/normalize/distill")
        print(f"dry-run complete; {len(pending_files)} files discovered")
        return 0

    if pending_files and not args.dry_run:
        _write_pre_ingest_checkpoint(paths, log.run_id, log.started_at)

    for src in pending_files:
        try:
            outcome = _process_one(src, paths, log.run_id, captured_at, args.distill_model)
        except Exception as exc:
            outcome = FileOutcome(
                pending_name=src.name,
                raw_path=None,
                normalized_path=None,
                routed_to="failed",
                category="unknown",
                error=f"orchestrator exception: {exc}",
            )
            log.overall_ok = False
        if outcome.routed_to == "failed" and outcome.error:
            log.overall_ok = False
        log.files.append(outcome)
        print(f"[{outcome.routed_to}] {outcome.pending_name} -> {outcome.normalized_path or outcome.raw_path}")

    log.finished_at = datetime.now(timezone.utc).isoformat()

    write_run_log(paths, log)

    if not args.no_commit and log.files:
        commit_msg = f"chore(ai-pipeline): ingest pending batch {captured_at.strftime('%Y-%m-%d')}"
        log.commit_hash = _commit_changes(root, commit_msg)

    return 0 if log.overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
