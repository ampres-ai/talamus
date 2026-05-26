from __future__ import annotations

from typing import Literal

Category = Literal["markdown", "text", "pdf", "epub", "image", "unknown"]

EXTENSION_MAP: dict[str, Category] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".pdf": "pdf",
    ".epub": "epub",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".bmp": "image",
    ".tiff": "image",
}
