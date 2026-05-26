from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@dataclass(frozen=True)
class ObsidianIssue:
    code: str
    path: str
    message: str


_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def _frontmatter(content: str) -> str:
    match = _FRONTMATTER_RE.match(content)
    return match.group(1) if match else ""


def _aliases_from_frontmatter(frontmatter: str) -> set[str]:
    aliases: set[str] = set()
    inline = re.search(r"^aliases:\s*\[(.*?)\]\s*$", frontmatter, re.MULTILINE)
    if inline:
        for item in inline.group(1).split(","):
            cleaned = item.strip().strip("\"'")
            if cleaned:
                aliases.add(cleaned)

    lines = frontmatter.splitlines()
    for idx, line in enumerate(lines):
        if not line.startswith("aliases:"):
            continue
        for nested in lines[idx + 1:]:
            if nested and not nested.startswith((" ", "\t", "-")):
                break
            match = re.match(r"\s*-\s*(.+?)\s*$", nested)
            if match:
                aliases.add(match.group(1).strip().strip("\"'"))
    return aliases


def collect_vault_targets(vault: Path) -> set[str]:
    targets: set[str] = set()
    for note in vault.glob("*.md"):
        content = note.read_text(encoding="utf-8")
        targets.add(note.stem)
        targets.add(note.stem.replace("-", " "))
        targets.update(_aliases_from_frontmatter(_frontmatter(content)))
    return targets


def _target_candidates(target: str) -> set[str]:
    cleaned = target.strip()
    return {
        cleaned,
        cleaned.replace(" ", "-"),
        cleaned.replace("-", " "),
    }


def _has_frontmatter_key(frontmatter: str, key: str) -> bool:
    return bool(re.search(rf"^{re.escape(key)}\s*:", frontmatter, re.MULTILINE))


def validate_note_content(
    path: str,
    content: str,
    existing_targets: set[str],
) -> list[ObsidianIssue]:
    issues: list[ObsidianIssue] = []
    frontmatter = _frontmatter(content)
    if not frontmatter:
        issues.append(ObsidianIssue("missing-frontmatter", path, "Note must start with YAML frontmatter."))
        return issues

    for key in ("type", "tags", "sources", "created", "updated"):
        if not _has_frontmatter_key(frontmatter, key):
            issues.append(ObsidianIssue(f"missing-{key}", path, f"Missing frontmatter field `{key}`."))

    if not _aliases_from_frontmatter(frontmatter):
        issues.append(ObsidianIssue("missing-aliases", path, "At least one alias is required."))

    if "raw_path:" not in frontmatter or "normalized_path:" not in frontmatter:
        issues.append(
            ObsidianIssue(
                "missing-provenance",
                path,
                "`sources` must include raw_path and normalized_path provenance.",
            )
        )

    for heading in ("## Summary", "## Core Idea", "## Practical Use", "## Related"):
        if heading not in content:
            issues.append(ObsidianIssue("missing-section", path, f"Missing required section `{heading}`."))

    for match in _WIKILINK_RE.finditer(content):
        target = match.group(1).strip()
        if not (_target_candidates(target) & existing_targets):
            issues.append(ObsidianIssue("broken-wikilink", path, f"Unresolved wikilink `{target}`."))

    return issues


def validate_vault(vault: Path) -> list[ObsidianIssue]:
    targets = collect_vault_targets(vault)
    issues: list[ObsidianIssue] = []
    for note in sorted(vault.glob("*.md")):
        content = note.read_text(encoding="utf-8")
        issues.extend(validate_note_content(note.name, content, targets))
    return issues
