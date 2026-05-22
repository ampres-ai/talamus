from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.fde_brain.categories import EXTENSION_MAP, Category


def classify(path: Path) -> Category:
    return EXTENSION_MAP.get(path.suffix.lower(), "unknown")
