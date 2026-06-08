#!/usr/bin/env python3
"""Hook Claude Code (SessionEnd/Stop): deposita la sessione di lavoro in Talamus.

Da registrare in Claude Code su un evento di fine sessione. Legge da stdin il JSON
dell'hook (con `transcript_path` e `cwd`), cattura `git diff`, e chiama
`talamus remember`. È **non invasivo**: se `TALAMUS_ROOT` non è impostato o non c'è un
transcript, non fa nulla. Imposta `TALAMUS_ROOT` alla cartella del tuo brain.
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
