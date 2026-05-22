from __future__ import annotations

from typing import Literal

Category = Literal["markdown", "text", "pdf", "image", "unknown"]

EXTENSION_MAP: dict[str, Category] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".bmp": "image",
    ".tiff": "image",
}
