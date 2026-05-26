"""Run distill_v3 on an already-normalized file without re-running normalize.

Used to recover when distill failed but normalize succeeded.

Usage:
    python -m tools.fde_brain.rerun_distill --root . --normalized "AI Space/normalized/pdf/<slug>.md"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.fde_brain.distill_v3 import distill_v3
from tools.fde_brain.paths import WorkspacePaths


_SLUG_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _title_to_filename(title: str) -> str:
    cleaned = _SLUG_SAFE_RE.sub("-", title).strip("-")
    return cleaned or "note"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-run distill_v3 on an existing normalized file.")
    parser.add_argument("--root", default=".", help="Workspace root.")
    parser.add_argument("--normalized", required=True, help="Path to the normalized markdown (relative to root).")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    paths = WorkspacePaths(root)
    normalized_path = (root / args.normalized).resolve()

    if not normalized_path.exists():
        print(f"ERROR: normalized file not found: {normalized_path}", file=sys.stderr)
        return 1

    run_id = uuid.uuid4().hex[:8]
    print(f"rerun_distill: run_id={run_id} normalized={args.normalized}", flush=True)

    result = distill_v3(normalized_path=normalized_path, paths=paths, run_id=run_id)
    if not result.ok:
        print(f"ERROR: distill failed: {result.error}", file=sys.stderr)
        return 1

    paths.fde_brain.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for note in result.notes:
        filename = f"{_title_to_filename(note.title)}.md"
        promoted_path = paths.fde_brain / filename
        promoted_path.write_text(note.content, encoding="utf-8")
        written.append(promoted_path)

    if paths.registry_path.exists():
        try:
            data = json.loads(paths.registry_path.read_text(encoding="utf-8"))
            for entry in data.get("entries", []):
                norm_paths = entry.get("normalized_paths", [])
                if args.normalized in norm_paths:
                    entry["promoted_to"] = [
                        p.relative_to(root).as_posix() for p in written
                    ]
                    entry["ingestion_run"] = run_id
            paths.registry_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"updated registry with {len(written)} promoted_to paths", flush=True)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: failed to update registry: {exc}", file=sys.stderr)

    print(f"done: {len(written)} notes written to FDE Brain", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
