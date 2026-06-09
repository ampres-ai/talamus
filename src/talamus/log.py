"""Lightweight logging for Talamus: quiet by default, verbose on demand.

Diagnostics go to stderr via the standard library `logging`. User-facing command
output stays on `print`; this is only for internal diagnostics.
"""

from __future__ import annotations

import logging
import os

_ROOT = "talamus"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a Talamus logger (a child of the `talamus` root logger)."""
    return logging.getLogger(_ROOT if name is None else f"{_ROOT}.{name}")


def configure(verbose: bool = False) -> None:
    """Set the logging level: DEBUG if `verbose` or env `TALAMUS_LOG` is set, else WARNING."""
    level = logging.DEBUG if verbose or os.environ.get("TALAMUS_LOG") else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    get_logger().setLevel(level)
