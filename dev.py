"""Dev checks for Talamus: lint, format, type-check, tests.

Usage:
    python dev.py          run all checks (lint, format, types, tests)
    python dev.py --fix    autofix lint + format first, then run all checks
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

# Hermetic tests: the global ontology (and anything else under TALAMUS_HOME)
# must never read from or write to the developer's real home during the gate.
# CODEX_HOME likewise: mcp-install tests would otherwise register the MCP
# server into the developer's real ~/.codex/config.toml via the codex CLI.
_TEST_HOME = tempfile.mkdtemp(prefix="talamus-gate-home-")
_TEST_CODEX_HOME = tempfile.mkdtemp(prefix="talamus-gate-codex-home-")


def _env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) if not pythonpath else f"{SRC}{os.pathsep}{pythonpath}"
    env["TALAMUS_HOME"] = _TEST_HOME
    env["CODEX_HOME"] = _TEST_CODEX_HOME
    return env


def run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=ROOT, env=_env())


def main() -> int:
    if "--fix" in sys.argv:
        run(["ruff", "check", "--fix", "src", "tests", "benchmarks"])
        run(["ruff", "format", "src", "tests", "benchmarks"])

    checks = [
        # benchmarks/ is dev-only (competitor deps) — linted/formatted but mypy
        # stays on src (the shipped, fully-typed package)
        ["ruff", "check", "src", "tests", "benchmarks"],
        ["ruff", "format", "--check", "src", "tests", "benchmarks"],
        ["mypy", "src"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
    ]
    failed = 0
    for cmd in checks:
        if run(cmd) != 0:
            failed = 1
    print("\nALL GREEN" if failed == 0 else "\nFAILED", flush=True)
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
