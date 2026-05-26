from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ollama

from tools.fde_brain.paths import WorkspacePaths
from tools.fde_brain.validate_obsidian import collect_vault_targets, validate_note_content


DEFAULT_DISTILL_MODEL = "gemma4:e4b"
MIN_NOTE_CONFIDENCE = 0.55
MAX_SECTION_CHARS = 12000


DISTILL_PROMPT = """You are curating an Obsidian LLM Wiki for Forward Deployed AI Engineering.

Extract only stable, reusable knowledge. Prefer reusable patterns, decision
frameworks, implementation methods, glossary concepts, and operational playbooks.
Return no notes for personal reminders, copyright pages, tables of contents, or
content that is not reusable.

Output strict JSON only:
{{
  "notes": [
    {{
      "title": "Canonical title",
      "type": "concept|framework|operation|method|pattern|glossary",
      "aliases": ["search term", "alternate term"],
      "summary": "short dense summary",
      "core_idea": "what is true and why it matters",
      "practical_use": "how an AI engineer/FDAI engineer would apply it",
      "related": ["Existing or new related concept title"],
      "tags": ["ai-engineering"],
      "confidence": 0.0,
      "supported_claims": ["claim grounded in the section"]
    }}
  ]
}}

Section provenance:
{provenance}

--- BEGIN SECTION ---
{content}
--- END SECTION ---
"""


@dataclass(frozen=True)
class LocalPromotedNote:
    title: str
    type: str
    content: str
    source_section: Path
    confidence: float


@dataclass(frozen=True)
class LocalDistillResult:
    ok: bool
    notes: list[LocalPromotedNote] = field(default_factory=list)
    raw_responses: list[str] = field(default_factory=list)
    review_items: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?```\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def _yaml_scalar(value: str) -> str:
    text = str(value)
    if text == "":
        return '""'
    needs_quotes = (
        ": " in text
        or text.startswith(("-", "?", ":", "@", "`", "!", "&", "*", "#", "{", "}", "[", "]"))
        or "\n" in text
        or text.strip() != text
    )
    if not needs_quotes:
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _FENCE_RE.sub("", stripped).strip()
    return stripped


def _parse_frontmatter(content: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith((" ", "\t", "-")):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _body_without_frontmatter(content: str) -> str:
    return _FRONTMATTER_RE.sub("", content, count=1).strip()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _slug_title(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title.strip()).strip("-")
    return slug or "Note"


def _yaml_list(values: list[str], indent: str = "  ") -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    if not cleaned:
        return f"{indent}- "
    return "\n".join(f"{indent}- {_yaml_scalar(value)}" for value in cleaned)


def _resolve_related_link(title: str, known_targets: set[str], produced_titles: set[str]) -> str:
    cleaned = title.strip()
    if not cleaned:
        return ""
    produced_slug = _slug_title(cleaned)
    if cleaned in produced_titles:
        return f"[[{produced_slug}|{cleaned}]]"
    candidates = [cleaned, cleaned.replace(" ", "-"), cleaned.replace("-", " ")]
    for candidate in candidates:
        if candidate in known_targets:
            target = candidate.replace(" ", "-") if candidate == cleaned and " " in candidate else candidate
            return f"[[{target}|{cleaned}]]" if target != cleaned else f"[[{target}]]"
    hyphen = cleaned.replace(" ", "-")
    if hyphen in known_targets:
        return f"[[{hyphen}|{cleaned}]]"
    return cleaned


def _render_note(
    candidate: dict[str, Any],
    section_path: Path,
    section_meta: dict[str, str],
    paths: WorkspacePaths,
    run_id: str,
    known_targets: set[str],
    produced_titles: set[str],
) -> str:
    title = str(candidate.get("title") or "").strip()
    aliases = [str(v).strip() for v in candidate.get("aliases") or [] if str(v).strip()]
    if title and title not in aliases:
        aliases.insert(0, title)
    tags = [str(v).lstrip("#").strip() for v in candidate.get("tags") or ["ai-engineering"] if str(v).strip()]
    now = datetime.now(timezone.utc).isoformat()
    supported_claims = [str(v).strip() for v in candidate.get("supported_claims") or [] if str(v).strip()]
    related = [
        _resolve_related_link(str(value), known_targets, produced_titles)
        for value in candidate.get("related") or []
    ]
    related = [value for value in related if value]

    source_raw = section_meta.get("source-path", "")
    source_hash = section_meta.get("source-hash", "")
    locator = section_meta.get("source-location", "")
    normalized_rel = _rel(section_path, paths.root)

    return (
        "---\n"
        f"type: {candidate.get('type') or 'concept'}\n"
        "status: evergreen\n"
        "aliases:\n"
        f"{_yaml_list(aliases)}\n"
        "tags:\n"
        f"{_yaml_list(tags)}\n"
        "sources:\n"
        f"  - raw_path: {_yaml_scalar(source_raw)}\n"
        f"    normalized_path: {_yaml_scalar(normalized_rel)}\n"
        f"    locator: {_yaml_scalar(locator)}\n"
        f"    source_hash: {_yaml_scalar(source_hash)}\n"
        "    supported_claims:\n"
        f"{_yaml_list(supported_claims, indent='      ')}\n"
        f"created: {now}\n"
        f"updated: {now}\n"
        f"ingestion_run: {run_id}\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Summary\n\n"
        f"{str(candidate.get('summary') or '').strip()}\n\n"
        "## Core Idea\n\n"
        f"{str(candidate.get('core_idea') or '').strip()}\n\n"
        "## Practical Use\n\n"
        f"{str(candidate.get('practical_use') or '').strip()}\n\n"
        "## Related\n\n"
        + ("\n".join(f"- {item}" for item in related) if related else "- \n")
        + "\n"
    )


def _call_ollama(prompt: str, model: str) -> str:
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0, "num_ctx": 16384},
    )
    return str(response["message"]["content"]).strip()


def _parse_payload(response: str) -> list[dict[str, Any]]:
    payload = json.loads(_strip_json_fence(response))
    notes = payload.get("notes", [])
    if not isinstance(notes, list):
        raise ValueError("notes field is not a list")
    return [note for note in notes if isinstance(note, dict)]


def distill_normalized_sections(
    section_paths: list[Path],
    paths: WorkspacePaths,
    run_id: str,
    model: str = DEFAULT_DISTILL_MODEL,
    existing_targets: set[str] | None = None,
) -> LocalDistillResult:
    known_targets = set(existing_targets or collect_vault_targets(paths.fde_brain))
    raw_responses: list[str] = []
    review_items: list[dict[str, Any]] = []
    raw_candidates: list[tuple[Path, dict[str, str], dict[str, Any]]] = []

    for section_path in section_paths:
        try:
            content = section_path.read_text(encoding="utf-8")
        except OSError as exc:
            review_items.append({"path": section_path.as_posix(), "error": f"read failed: {exc}"})
            continue
        meta = _parse_frontmatter(content)
        body = _body_without_frontmatter(content)
        if len(body) > MAX_SECTION_CHARS:
            body = body[:MAX_SECTION_CHARS] + "\n\n[Truncated to token budget for local distillation.]"
        prompt = DISTILL_PROMPT.format(
            provenance=json.dumps(meta, indent=2, ensure_ascii=False),
            content=body,
        )
        try:
            response = _call_ollama(prompt, model=model)
            raw_responses.append(response)
            candidates = _parse_payload(response)
        except Exception as exc:
            review_items.append({"path": _rel(section_path, paths.root), "error": f"json/model error: {exc}"})
            continue
        for candidate in candidates:
            confidence = float(candidate.get("confidence") or 0)
            title = str(candidate.get("title") or "").strip()
            if not title or confidence < MIN_NOTE_CONFIDENCE:
                review_items.append({
                    "path": _rel(section_path, paths.root),
                    "title": title,
                    "error": f"low confidence: {confidence}",
                })
                continue
            raw_candidates.append((section_path, meta, candidate))

    produced_titles = {str(candidate.get("title") or "").strip() for _, _, candidate in raw_candidates}
    notes: list[LocalPromotedNote] = []
    for section_path, meta, candidate in raw_candidates:
        title = str(candidate.get("title") or "").strip()
        content = _render_note(
            candidate=candidate,
            section_path=section_path,
            section_meta=meta,
            paths=paths,
            run_id=run_id,
            known_targets=known_targets,
            produced_titles=produced_titles,
        )
        validation_targets = known_targets | {_slug_title(t) for t in produced_titles} | produced_titles
        issues = validate_note_content(f"{_slug_title(title)}.md", content, validation_targets)
        blocking = [issue for issue in issues if issue.code not in {"broken-wikilink"}]
        if blocking:
            review_items.append({
                "path": _rel(section_path, paths.root),
                "title": title,
                "error": "; ".join(issue.message for issue in blocking),
            })
            continue
        notes.append(
            LocalPromotedNote(
                title=title,
                type=str(candidate.get("type") or "concept"),
                content=content,
                source_section=section_path,
                confidence=float(candidate.get("confidence") or 0),
            )
        )

    return LocalDistillResult(ok=True, notes=notes, raw_responses=raw_responses, review_items=review_items)
