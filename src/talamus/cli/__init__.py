"""Talamus CLI package (split from the former single cli.py module)."""

from __future__ import annotations

from talamus.cli._common import _ensure_utf8_output, _resolve_root
from talamus.cli.app import main
from talamus.cli.parser import build_parser

__all__ = ["main", "build_parser", "_ensure_utf8_output", "_resolve_root"]
