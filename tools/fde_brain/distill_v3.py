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


VALID_TYPES = {"overview", "chapter", "concept", "framework", "operation", "method", "pattern", "glossary"}


DISTILL_CHUNK_PROMPT = """You are an Obsidian wiki curator working on a knowledge graph.

Read the macro-chapter below from a normalized source. Extract 0..N atomic
notes that are worth promoting to a curated wiki. Empty list is OK and
preferred when the chunk is administrative (cover, copyright, ToC, etc.).

Each note MUST be:
- a stable, reusable concept / framework / operation / method / pattern / glossary term
- worded with practitioner voice and density (no filler)
- titled with a short, canonical name (NOT "Chapter 3: ...")

Notes MAY:
- fuse content from multiple subsections within this chunk (cite all heading
  anchors you draw from in `source_anchors`)
- reference other notes via [[Wikilinks]] using canonical titles

Output STRICTLY this JSON shape, nothing else:
{{
  "notes": [
    {{
      "title": "Short canonical concept name",
      "type": "concept" | "framework" | "operation" | "method" | "pattern" | "glossary",
      "body": "markdown body (no frontmatter); may contain [[wikilinks]]",
      "source_anchors": ["{normalized_rel}#anchor-a", "{normalized_rel}#anchor-b"],
      "tags": ["..."]
    }}
  ]
}}

Chapter heading: {chapter_title}
Chunk anchor: {normalized_rel}#{chapter_anchor}

--- BEGIN CHUNK ---
{chunk_body}
--- END CHUNK ---
"""


OVERVIEW_PROMPT = """You curated the following notes from a single normalized source.
Produce exactly ONE overview note that wikilinks the most important ones.

Output STRICTLY this JSON, nothing else:
{{
  "notes": [
    {{
      "title": "{source_title} Overview",
      "type": "overview",
      "body": "markdown body. Use [[Note Title]] wikilinks ONLY to titles from the list below.",
      "source_anchors": ["{normalized_rel}"],
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
class DistillV3Result:
    ok: bool
    notes: list[PromotedNote] = field(default_factory=list)
    raw_responses: list[str] = field(default_factory=list)
    audit: dict = field(default_factory=dict)
    error: str | None = None


_L1_HEADING_RE = re.compile(r"^##[ \t]+(?!Page\b)(.+?)\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?```\s*$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]")


def _strip_code_fence(response: str) -> str:
    stripped = response.strip()
    if stripped.startswith("```"):
        stripped = _FENCE_RE.sub("", stripped).strip()
    return stripped


def _parse_notes_payload(stdout: str) -> list[dict]:
    response = _strip_code_fence(stdout)
    if not response:
        return []
    data = json.loads(response)
    notes = data.get("notes", [])
    if not isinstance(notes, list):
        raise ValueError("notes field is not a list")
    return notes


def _normalized_relative(normalized_path: Path, paths: WorkspacePaths) -> str:
    try:
        return normalized_path.relative_to(paths.root).as_posix()
    except ValueError:
        return normalized_path.as_posix()


def _split_into_l1_chunks(content: str) -> list[tuple[str, str, str]]:
    """Return list of (title, anchor, body) for each L1 (##) chapter section."""
    matches = list(_L1_HEADING_RE.finditer(content))
    if not matches:
        return []
    chunks: list[tuple[str, str, str]] = []
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        chunks.append((title, chapter_anchor(title), body))
    return chunks


def _run_claude(prompt: str, timeout_sec: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )


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


def _validate_wikilinks(body: str, valid_titles: set[str]) -> tuple[str, list[str]]:
    valid_lower = {t.lower() for t in valid_titles}
    dropped: list[str] = []

    def _replace(match: re.Match) -> str:
        target = match.group(1).strip()
        alias = match.group(2)
        if target.lower() in valid_lower:
            return match.group(0)
        dropped.append(target)
        return alias.strip() if alias else target

    new_body = _WIKILINK_RE.sub(_replace, body)
    return new_body, dropped


def _write_audit(paths: WorkspacePaths, run_id: str, started_at: str, audit: dict) -> Path:
    paths.logs_decisions.mkdir(parents=True, exist_ok=True)
    safe = started_at.replace(":", "").split("+")[0].split(".")[0]
    out = paths.logs_decisions / f"{safe}-{run_id}-distill.json"
    out.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def distill_v3(
    normalized_path: Path,
    paths: WorkspacePaths,
    run_id: str,
    timeout_sec: int = 300,
) -> DistillV3Result:
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        content = normalized_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DistillV3Result(ok=False, error=f"failed to read normalized file: {exc}")

    normalized_rel = _normalized_relative(normalized_path, paths)
    source_slug = normalized_path.stem
    chunks = _split_into_l1_chunks(content)
    raw_responses: list[str] = []
    parsed_notes: list[dict] = []
    chunks_audit: list[dict] = []

    try:
        for chapter_title, anchor, body in chunks:
            prompt = DISTILL_CHUNK_PROMPT.format(
                normalized_rel=normalized_rel,
                chapter_title=chapter_title,
                chapter_anchor=anchor,
                chunk_body=body,
            )
            proc = _run_claude(prompt, timeout_sec)
            raw_responses.append(proc.stdout)
            if proc.returncode != 0:
                return DistillV3Result(
                    ok=False, raw_responses=raw_responses,
                    error=proc.stderr.strip() or f"claude exited {proc.returncode} on chunk '{chapter_title}'",
                )
            try:
                notes = _parse_notes_payload(proc.stdout)
            except json.JSONDecodeError as exc:
                return DistillV3Result(
                    ok=False, raw_responses=raw_responses,
                    error=f"json decode failed on chunk '{chapter_title}': {exc}",
                )
            valid_notes = [n for n in notes if isinstance(n, dict) and n.get("type") in VALID_TYPES]
            chunks_audit.append({
                "chapter_title": chapter_title,
                "anchor": anchor,
                "notes_returned": len(notes),
                "notes_valid": len(valid_notes),
            })
            parsed_notes.extend(valid_notes)

        if parsed_notes:
            titles_list = [{"title": n.get("title", ""), "type": n.get("type", "")} for n in parsed_notes if n.get("title")]
            overview_prompt = OVERVIEW_PROMPT.format(
                source_title=source_slug,
                normalized_rel=normalized_rel,
                notes_list=json.dumps(titles_list, indent=2, ensure_ascii=False),
            )
            proc = _run_claude(overview_prompt, timeout_sec)
            raw_responses.append(proc.stdout)
            if proc.returncode != 0:
                return DistillV3Result(
                    ok=False, raw_responses=raw_responses,
                    error=proc.stderr.strip() or f"claude exited {proc.returncode} on overview pass",
                )
            try:
                overview_notes = _parse_notes_payload(proc.stdout)
            except json.JSONDecodeError as exc:
                return DistillV3Result(
                    ok=False, raw_responses=raw_responses,
                    error=f"json decode failed on overview pass: {exc}",
                )
            for n in overview_notes:
                if isinstance(n, dict) and n.get("type") in VALID_TYPES:
                    parsed_notes.append(n)
    except subprocess.TimeoutExpired:
        return DistillV3Result(
            ok=False, raw_responses=raw_responses, error=f"claude cli timeout after {timeout_sec}s",
        )
    except FileNotFoundError as exc:
        return DistillV3Result(
            ok=False, raw_responses=raw_responses, error=f"claude binary not found: {exc}",
        )

    seen_titles: set[str] = set()
    note_records: list[dict] = []
    for note in parsed_notes:
        raw_title = (note.get("title") or "").strip()
        if not raw_title:
            continue
        title = raw_title if raw_title not in seen_titles else f"{raw_title} ({source_slug})"
        seen_titles.add(title)
        note_records.append({
            "title": title,
            "type": note["type"],
            "body": (note.get("body") or "").strip(),
            "source_anchors": note.get("source_anchors") or [normalized_rel],
            "tags": note.get("tags") or [],
        })

    title_set = {r["title"] for r in note_records}
    wikilinks_dropped: list[dict] = []
    for record in note_records:
        clean_body, dropped = _validate_wikilinks(record["body"], title_set)
        record["body"] = clean_body
        if dropped:
            wikilinks_dropped.append({"note": record["title"], "dropped": dropped})

    promoted: list[PromotedNote] = []
    for record in note_records:
        anchors = record["source_anchors"] if isinstance(record["source_anchors"], list) else [str(record["source_anchors"])]
        content_md = _render_note(
            title=record["title"],
            note_type=record["type"],
            body=record["body"],
            tags=record["tags"] if isinstance(record["tags"], list) else [],
            source_anchors=anchors,
            captured_at=started_at,
            run_id=run_id,
        )
        promoted.append(PromotedNote(
            title=record["title"],
            type=record["type"],
            content=content_md,
            source_anchors=list(anchors),
        ))

    audit = {
        "run_id": run_id,
        "started_at": started_at,
        "normalized_path": normalized_rel,
        "chunks_processed": len(chunks),
        "chunks": chunks_audit,
        "notes_total": len(promoted),
        "wikilinks_dropped": wikilinks_dropped,
    }
    try:
        _write_audit(paths, run_id, started_at, audit)
    except OSError:
        pass

    return DistillV3Result(ok=True, notes=promoted, raw_responses=raw_responses, audit=audit)
