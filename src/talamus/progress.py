"""Minimal progress reporting for long operations (PRD F8.5 substrate).

Renders ``[stage] done/total current · elapsed`` lines. Echo only when attached
to a TTY (no noise in pipes/tests); the full CLI output design lands with M8.
"""

from __future__ import annotations

import sys
import time


class Progress:
    def __init__(self, total: int, stage: str = "", echo: bool | None = None) -> None:
        self.total = total
        self.stage = stage
        self.done = 0
        self.started = time.perf_counter()
        self.echo = sys.stderr.isatty() if echo is None else echo

    def step(self, current: str = "") -> None:
        self.done += 1
        if self.echo:
            print(f"\r{self.line(current)}", end="", file=sys.stderr, flush=True)
            if self.done >= self.total:
                print(file=sys.stderr)

    def line(self, current: str = "") -> str:
        elapsed = time.perf_counter() - self.started
        stage = f"[{self.stage}] " if self.stage else ""
        suffix = f" {current}" if current else ""
        return f"{stage}{self.done}/{self.total}{suffix} · {elapsed:.0f}s"
