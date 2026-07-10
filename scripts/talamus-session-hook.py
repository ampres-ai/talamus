#!/usr/bin/env python3
"""Claude Code hook (SessionEnd/Stop): deposit the work session into Talamus.

Register it in Claude Code on a session-end event. It reads the hook JSON from
stdin (with `transcript_path` and `cwd`), captures `git diff`, and calls
`talamus remember`. It is **non-invasive**: when `TALAMUS_ROOT` is unset or no
transcript exists, it does nothing. Point `TALAMUS_ROOT` at your brain folder.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile


def main() -> int:
    brain = os.environ.get("TALAMUS_ROOT")
    if not brain:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    transcript_path = payload.get("transcript_path", "")
    cwd = payload.get("cwd") or os.getcwd()
    if not transcript_path or not os.path.isfile(transcript_path):
        return 0

    diff = ""
    try:
        diff = subprocess.run(
            ["git", "diff", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=30
        ).stdout
    except Exception:
        diff = ""

    diff_file = None
    if diff.strip():
        handle = tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False, encoding="utf-8")
        handle.write(diff)
        handle.close()
        diff_file = handle.name

    args = [sys.executable, "-m", "talamus.cli", "remember",
            "--transcript", transcript_path, "--root", brain]
    if diff_file:
        args += ["--diff", diff_file]
    try:
        subprocess.run(args, timeout=600)
    except Exception:
        pass
    finally:
        if diff_file and os.path.exists(diff_file):
            os.remove(diff_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
