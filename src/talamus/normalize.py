from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class NormalizedSection:
    section_id: str
    title: str
    text: str


@dataclass(frozen=True)
class NormalizedPackage:
    raw_path: str
    source_hash: str
    sections: list[NormalizedSection]


def normalize_text(raw_path: str, text: str) -> NormalizedPackage:
    source_hash = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    fallback_title = PurePosixPath(raw_path).name
    sections: list[NormalizedSection] = []
    matches = list(re.finditer(r"^#\s+(.+)$", text, flags=re.MULTILINE))
    if not matches:
        sections.append(NormalizedSection("001", fallback_title, text.strip()))
        return NormalizedPackage(raw_path, source_hash, sections)
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append(NormalizedSection(f"{index + 1:03d}", match.group(1).strip(), body))
    return NormalizedPackage(raw_path, source_hash, sections)
