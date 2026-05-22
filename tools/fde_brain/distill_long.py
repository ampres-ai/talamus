from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.fde_brain.chapters import chapter_anchor
from tools.fde_brain.paths import WorkspacePaths


VALID_TYPES = {"overview", "chapter", "pattern", "glossary", "concept"}


CHAPTER_PROMPT = """You are an Obsidian wiki curator. Given a single chapter from a longer source,
produce a JSON object describing the durable notes worth promoting to a curated wiki.

Output STRICTLY this JSON shape, nothing else:
{{
  "notes": [
    {{
      "title": "...",
      "type": "chapter" | "concept",
      "body": "markdown body without frontmatter",
      "tags": ["..."],
      "anchor_used": "{anchor}"
    }}
  ]
}}

Rules:
- Emit one note with type=chapter that captures the chapter's main idea (~600 words max).
- Emit 0-5 notes with type=concept for atomic ideas that deserve their own page.
- Titles are short, plain English concept names. NO "Chapter N: ...".
- Bodies favor density and practitioner voice. No filler.
- Wikilinks ([[Other Note]]) are allowed if they reference a title you also produce.
- If the chapter is shallow, return {{"notes": []}}.

Chapter title: {title}
Anchor (do not change): {anchor}

--- BEGIN CHAPTER ---
{body}
--- END CHAPTER ---
"""


CROSS_PROMPT = """You are an Obsidian wiki curator. Given the full normalized source below,
produce JSON listing reusable cross-cutting notes.

Output STRICTLY this JSON, nothing else:
{{
  "notes": [
    {{
      "title": "...",
      "type": "pattern" | "glossary",
      "body": "markdown body without frontmatter",
      "tags": ["..."]
    }}
  ]
}}

Rules:
- type=pattern: design patterns, frameworks, decision rules, techniques recurring across the source.
- type=glossary: key terms with concise definitions.
- 0-8 notes total. Skip if nothing reusable.

--- BEGIN SOURCE ---
{body}
--- END SOURCE ---
"""


OVERVIEW_PROMPT = """You curated the following notes from a single source. Produce exactly ONE
overview note that wikilinks to them.

Output STRICTLY this JSON, nothing else:
{{
  "notes": [
    {{
      "title": "{source_title} Overview",
      "type": "overview",
      "body": "markdown body. Use [[Note Title]] wikilinks to the notes listed below.",
      "tags": ["overview"]
    }}
  ]
}}

Notes produced:
{notes_list}
"""


@dataclass(frozen=True)
class PromotedNote:
    title: str
    type: str
    content: str
    source_anchors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LongDistillResult:
    ok: bool
    notes: list[PromotedNote] = field(default_factory=list)
    raw_responses: list[str] = field(default_factory=list)
    error: str | None = None


_CHAPTER_HEADING_RE = re.compile(r"^(#{2,})\s+(?!Page\b)(.+?)\s*$", re.MULTILINE)


def _slug_from_normalized(normalized_path: Path) -> str:
    return normalized_path.stem


def _normalized_relative(normalized_path: Path, paths: WorkspacePaths) -> str:
    try:
        return normalized_path.relative_to(paths.root).as_posix()
    except ValueError:
        return normalized_path.as_posix()


def _extract_chapter_sections(content: str) -> list[tuple[str, str, str]]:
    """Return list of (title, anchor, body) for each chapter heading."""
    matches = list(_CHAPTER_HEADING_RE.finditer(content))
    if not matches:
        return []
    sections: list[tuple[str, str, str]] = []
    for idx, match in enumerate(matches):
        title = match.group(2).strip()
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        sections.append((title, chapter_anchor(title), body))
    return sections


def _run_claude(prompt: str, timeout_sec: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )


def _parse_notes_payload(stdout: str) -> list[dict]:
    response = stdout.strip()
    if not response:
        return []
    data = json.loads(response)
    notes = data.get("notes", [])
    if not isinstance(notes, list):
        raise ValueError("notes field is not a list")
    return notes


def _render_note(
    title: str,
    note_type: str,
    body: str,
    tags: list[str],
    source_anchors: list[str],
    captured_at: str,
    run_id: str,
) -> str:
    sources_yaml = "\n".join(f"  - {anchor}" for anchor in source_anchors) or "  - "
    tags_yaml = ", ".join(tags)
    return (
        "---\n"
        f"type: {note_type}\n"
        f"tags: [{tags_yaml}]\n"
        "sources:\n"
        f"{sources_yaml}\n"
        f"captured-at: {captured_at}\n"
        f"ingestion-run: {run_id}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{body}\n"
    )


def distill_long_source(
    normalized_path: Path,
    raw_path: Path,
    paths: WorkspacePaths,
    run_id: str,
    timeout_sec: int = 300,
) -> LongDistillResult:
    try:
        content = normalized_path.read_text(encoding="utf-8")
    except OSError as exc:
        return LongDistillResult(ok=False, error=f"failed to read normalized file: {exc}")

    chapter_sections = _extract_chapter_sections(content)
    normalized_rel = _normalized_relative(normalized_path, paths)
    source_slug = _slug_from_normalized(normalized_path)
    captured_at = datetime.now(timezone.utc).isoformat()
    raw_responses: list[str] = []
    parsed_notes: list[dict] = []
    chapter_anchors_by_note: dict[int, str] = {}

    def _add_notes(notes: list[dict], anchor: str | None) -> None:
        for note in notes:
            if not isinstance(note, dict):
                continue
            note_type = note.get("type")
            if note_type not in VALID_TYPES:
                continue
            idx = len(parsed_notes)
            parsed_notes.append(note)
            chapter_anchors_by_note[idx] = anchor or ""

    try:
        for title, anchor, body in chapter_sections:
            prompt = CHAPTER_PROMPT.format(title=title, anchor=anchor, body=body)
            proc = _run_claude(prompt, timeout_sec)
            raw_responses.append(proc.stdout)
            if proc.returncode != 0:
                return LongDistillResult(
                    ok=False, raw_responses=raw_responses,
                    error=proc.stderr.strip() or f"claude exited {proc.returncode} on chapter '{title}'",
                )
            _add_notes(_parse_notes_payload(proc.stdout), anchor)

        cross_prompt = CROSS_PROMPT.format(body=content)
        proc = _run_claude(cross_prompt, timeout_sec)
        raw_responses.append(proc.stdout)
        if proc.returncode != 0:
            return LongDistillResult(
                ok=False, raw_responses=raw_responses,
                error=proc.stderr.strip() or f"claude exited {proc.returncode} on cross pass",
            )
        _add_notes(_parse_notes_payload(proc.stdout), None)

        notes_for_overview = [
            {"title": n.get("title", ""), "type": n.get("type", "")}
            for n in parsed_notes
            if n.get("title")
        ]
        overview_prompt = OVERVIEW_PROMPT.format(
            source_title=source_slug,
            notes_list=json.dumps(notes_for_overview, indent=2, ensure_ascii=False),
        )
        proc = _run_claude(overview_prompt, timeout_sec)
        raw_responses.append(proc.stdout)
        if proc.returncode != 0:
            return LongDistillResult(
                ok=False, raw_responses=raw_responses,
                error=proc.stderr.strip() or f"claude exited {proc.returncode} on overview pass",
            )
        _add_notes(_parse_notes_payload(proc.stdout), None)
    except subprocess.TimeoutExpired:
        return LongDistillResult(
            ok=False, raw_responses=raw_responses, error=f"claude cli timeout after {timeout_sec}s",
        )
    except json.JSONDecodeError as exc:
        return LongDistillResult(
            ok=False, raw_responses=raw_responses, error=f"json decode failed: {exc}",
        )
    except FileNotFoundError as exc:
        return LongDistillResult(
            ok=False, raw_responses=raw_responses, error=f"claude binary not found: {exc}",
        )

    promoted: list[PromotedNote] = []
    seen_titles: set[str] = set()
    for idx, note in enumerate(parsed_notes):
        raw_title = (note.get("title") or "").strip()
        if not raw_title:
            continue
        title = raw_title if raw_title not in seen_titles else f"{raw_title} ({source_slug})"
        seen_titles.add(title)

        note_type = note["type"]
        body = (note.get("body") or "").strip()
        tags = note.get("tags") or []
        if not isinstance(tags, list):
            tags = []

        chapter_anchor_value = chapter_anchors_by_note.get(idx, "")
        if chapter_anchor_value:
            anchor_locator = f"{normalized_rel}#{chapter_anchor_value}"
        else:
            anchor_locator = normalized_rel
        source_anchors = [anchor_locator]

        content_md = _render_note(
            title=title,
            note_type=note_type,
            body=body,
            tags=tags,
            source_anchors=source_anchors,
            captured_at=captured_at,
            run_id=run_id,
        )
        promoted.append(
            PromotedNote(
                title=title,
                type=note_type,
                content=content_md,
                source_anchors=source_anchors,
            )
        )

    return LongDistillResult(ok=True, notes=promoted, raw_responses=raw_responses)
