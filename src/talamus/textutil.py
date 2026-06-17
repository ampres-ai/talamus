"""Light text utilities: tokenization with a small bilingual (IT+EN) stemmer.

Retrieval tokenized on raw words misses inflections: a query for "spezzare" would
not match a note that says "spezza". A light suffix-stripping stemmer collapses the
common Italian AND English inflections (real brains mix both languages — measured
as the dominant failure class in the 2026-06 recall research) so the two meet.
Applied symmetrically to indexed text and query. The English pass runs between two
Italian passes so pairs like "note"/"notes" land on the same stem.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9][a-z0-9-]{2,}")

# Tried longest-first; never strips below a 3-character stem.
_SUFFIXES = (
    "amento",
    "azione",
    "zione",
    "mente",
    "abile",
    "ibile",
    "ista",
    "ismo",
    "are",
    "ere",
    "ire",
    "ato",
    "ata",
    "ati",
    "ate",
    "ito",
    "ita",
    "iti",
    "ite",
    "oso",
    "osa",
    "osi",
    "ose",
    "ico",
    "ica",
    "ici",
    "iche",
    "che",
    "ghe",
    "i",
    "e",
    "o",
    "a",
)


# English pass: tried longest-first; never strips below a 4-character stem.
_EN_SUFFIXES = (
    "ations",
    "ation",
    "ements",
    "ement",
    "ities",
    "ings",
    "ity",
    "able",
    "ing",
    "ive",
    "ed",
    "es",
    "ly",
    "al",
    "s",
)


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _stem_en(word: str) -> str:
    for suffix in _EN_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokens(text: str) -> list[str]:
    """Lowercase word tokens, lightly stemmed (Italian + English)."""
    return [_stem(_stem_en(_stem(match))) for match in _TOKEN.findall(text.lower())]


_NON_ASCII_LETTER = re.compile(r"[à-ÿ]")


def non_ascii_ratio(texts: list[str]) -> float:
    """Fraction of RAW texts containing a non-ASCII (accented) letter — a cheap,
    deterministic proxy for a non-English / multi-script corpus. Must run on raw
    text, not on `tokens()` output (the tokenizer strips accented characters)."""
    if not texts:
        return 0.0
    hits = sum(1 for t in texts if _NON_ASCII_LETTER.search(t or ""))
    return round(hits / len(texts), 4)


def is_monolingual_ascii(texts: list[str], threshold: float = 0.05) -> bool:
    """True when the corpus is effectively single-script ASCII (English-like),
    where the trigram cognate bridge adds noise and can be down-weighted. The
    threshold is intentionally low: a handful of accented words must NOT flip a
    genuinely English corpus."""
    return non_ascii_ratio(texts) < threshold
