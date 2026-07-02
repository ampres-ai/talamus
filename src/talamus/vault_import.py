"""Markdown/Obsidian vault importer — migration without the LLM (P9 minimal slice).

Imports a folder of .md notes 1:1: titles, tags, aliases and ``[[wikilinks]]``
preserved, wikilinks doubling as typed graph relations. NO LLM call is made —
migration must be instant, free and light (the switching wall falls without
burning the user's subscription). The moats still apply on top: every imported
note carries a SourceRef with a content hash (verifiability) and enters the
bitemporal store like any other note. Obsidian is the primary flavor; a Notion
markdown export is the same shape, so one code path covers both.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from talamus.errors import SourceNotFound
from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote, Relation, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import load_notes, rebuild_indexes, render_note_markdown, write_note_json

_SKIP_DIRS = {".obsidian", ".trash", ".git", ".talamus"}
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_SUMMARY_CHARS = 240


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Extract a minimal YAML-ish frontmatter (title/tags/aliases) and the body.

    Deliberately NOT a YAML parser (no new dependency, and vault frontmatter is
    routinely malformed): only the simple `key: value`, `key: [a, b]` and
    `key:\\n  - item` shapes are read; anything else is ignored, never fatal."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    header, body = text[3:end], text[end + 4 :]
    meta: dict[str, object] = {}
    current_list: list[str] | None = None
    for raw_line in header.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        item = re.match(r"^\s+-\s*(.+)$", line)
        if item and current_list is not None:
            current_list.append(item.group(1).strip().strip("\"'"))
            continue
        pair = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not pair:
            current_list = None
            continue
        key, value = pair.group(1).lower(), pair.group(2).strip()
        if not value:
            current_list = []
            meta[key] = current_list
            continue
        current_list = None
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip("\"'")
    return meta, body


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _first_paragraph(body: str) -> str:
    for block in body.split("\n\n"):
        text = " ".join(block.split())
        if text and not text.startswith("#"):
            return text[:_SUMMARY_CHARS]
    return ""


def _note_from_file(vault: Path, file_path: Path, text: str) -> CanonicalNote:
    meta, body = _split_frontmatter(text)
    title = str(meta.get("title", "") or "").strip() or file_path.stem
    # a malformed frontmatter can leak YAML fragments into the title — keep it sane
    if any(ch in title for ch in "[]{}\n"):
        title = file_path.stem
    aliases = _as_list(meta.get("aliases"))
    tags = [t.lstrip("#") for t in _as_list(meta.get("tags"))]
    body = body.strip()
    summary = _first_paragraph(body) or f"{title}."
    links = list(dict.fromkeys(m.group(1).strip() for m in _WIKILINK.finditer(body)))
    relations = [
        Relation(source=title, relation="links-to", target=target, confidence=1.0)
        for target in links
        if target and target != title
    ]
    rel_path = file_path.relative_to(vault).as_posix()
    folder = Path(rel_path).parent.as_posix()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source = SourceRef(
        raw_path=rel_path,
        normalized_path=rel_path,
        locator=f"imported from vault: {rel_path}",
        source_hash=f"sha256:{digest}",
        supported_claims=[],
    )
    retrieval = " ".join([title, *aliases, *tags, summary])
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=aliases,
        folder="" if folder == "." else folder,
        tags=tags,
        summary=summary,
        retrieval_text=retrieval,
        body_sections={"content": body},
        proposed_links=[],
        relations=relations,
        sources=[source],
        confidence=1.0,  # human-written note, imported verbatim
    )


def _hash_registry(paths: TalamusPaths) -> Path:
    return paths.cache / "imported-vault.json"


def _load_hashes(paths: TalamusPaths) -> dict:
    path = _hash_registry(paths)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_hashes(paths: TalamusPaths, hashes: dict) -> None:
    paths.cache.mkdir(parents=True, exist_ok=True)
    _hash_registry(paths).write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def _vault_files(vault: Path) -> list[Path]:
    files = []
    for path in sorted(vault.rglob("*.md")):
        parts = set(path.relative_to(vault).parts[:-1])
        if parts & _SKIP_DIRS or any(p.startswith(".") for p in parts):
            continue
        files.append(path)
    return files


def import_vault(paths: TalamusPaths, vault_dir: str | Path) -> dict:
    """Import every markdown note of a vault 1:1. Returns a report dict.

    Idempotent (per-file content hash in .talamus/cache/imported-vault.json);
    duplicate titles keep the FIRST note and report the rest; originals are
    copied under raw/vault/ so verify has something to check against."""
    vault = Path(vault_dir).expanduser()
    if not vault.is_dir():
        raise SourceNotFound(vault)
    paths.ensure_directories()
    hashes = _load_hashes(paths)
    seen_ids = {n.note_id for n in load_notes(paths)}
    written: list[CanonicalNote] = []
    duplicates: list[str] = []
    failed: list[dict] = []
    skipped = 0
    for file_path in _vault_files(vault):
        rel = file_path.relative_to(vault).as_posix()
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            failed.append({"file": rel, "error": str(exc)})
            continue
        if not text.strip():
            skipped += 1
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if hashes.get(rel) == digest:
            skipped += 1
            continue
        note = _note_from_file(vault, file_path, text)
        if note.note_id in seen_ids:
            duplicates.append(rel)
            continue
        raw_copy = paths.raw / "vault" / rel
        raw_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file_path, raw_copy)
        write_note_json(paths, note)
        seen_ids.add(note.note_id)
        hashes[rel] = digest
        written.append(note)
    if written:
        # render with a registry of the WHOLE batch so same-vault wikilinks resolve
        registry = NoteRegistry.from_notes(load_notes(paths))
        for note in written:
            render_note_markdown(paths, note, registry)
        rebuild_indexes(paths)
    _save_hashes(paths, hashes)
    return {
        "notes_written": len(written),
        "skipped": skipped,
        "duplicates": duplicates,
        "failed": failed,
        "source": str(vault),
    }
