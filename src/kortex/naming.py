from __future__ import annotations

import re

# Caratteri non ammessi nei nomi file su Windows (e '/' ovunque), piu i controlli.
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def note_slug(title: str) -> str:
    """Trasforma un titolo in uno slug sicuro per i nomi file su ogni OS."""
    slug = _INVALID_FILENAME.sub("", title.strip())
    slug = re.sub(r"\s+", "-", slug)
    slug = slug.strip(". ")
    return slug or "untitled"


def note_filename(title: str) -> str:
    return note_slug(title) + ".md"
