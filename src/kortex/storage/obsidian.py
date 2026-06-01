from __future__ import annotations

import re

from kortex.linking import NoteRegistry, resolve_links
from kortex.models import CanonicalNote


def _yaml_list(values: list[str], indent: int = 2) -> str:
    prefix = " " * indent
    if not values:
        return f"{prefix}[]"
    return "\n".join(f"{prefix}- {value}" for value in values)


def _heading(name: str) -> str:
    words = re.sub(r"[_-]+", " ", name).split()
    return " ".join(word.capitalize() for word in words)


def _apply_links(text: str, links: dict[str, str]) -> str:
    linked = text
    for anchor, wikilink in sorted(links.items(), key=lambda item: len(item[0]), reverse=True):
        linked = re.sub(rf"\b{re.escape(anchor)}\b", wikilink, linked, count=1)
    return linked


def render_obsidian_note(note: CanonicalNote, registry: NoteRegistry) -> str:
    links = resolve_links(note, registry)
    lines = [
        "---",
        f"id: {note.note_id}",
        f"title: {note.title}",
        "aliases:",
        _yaml_list(note.aliases),
        "tags:",
        _yaml_list(note.tags),
        f"confidence: {note.confidence}",
        "sources:",
    ]
    for source in note.sources:
        lines.extend(
            [
                f"  - raw_path: {source.raw_path}",
                f"    normalized_path: {source.normalized_path}",
                f"    locator: {source.locator}",
                f"    source_hash: {source.source_hash}",
                "    supported_claims:",
                _yaml_list(source.supported_claims, indent=6),
            ]
        )
    lines.extend(["---", "", f"# {note.title}", "", "## Summary", "", note.summary, ""])
    for section_name, section_text in note.body_sections.items():
        lines.extend([f"## {_heading(section_name)}", "", _apply_links(section_text, links), ""])
    if links:
        lines.extend(["## Related", ""])
        for wikilink in sorted(set(links.values())):
            lines.append(f"- {wikilink}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
