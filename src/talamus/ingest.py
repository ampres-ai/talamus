from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from talamus.adapters.llm import LLMProvider
from talamus.extract import extract_notes
from talamus.linking import NoteRegistry
from talamus.normalize import NormalizedPackage, normalize_text
from talamus.paths import TalamusPaths
from talamus.session import normalize_session, session_worth_remembering
from talamus.sources import extract_text, is_url, read_url
from talamus.store import load_notes, rebuild_indexes, render_note_markdown, write_note_json

_SUPPORTED = {".md", ".markdown", ".txt", ".rst", ".pdf", ".docx", ".html", ".htm"}


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_hashes(paths: TalamusPaths) -> dict:
    path = paths.cache / "ingested.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _save_hashes(paths: TalamusPaths, hashes: dict) -> None:
    paths.cache.mkdir(parents=True, exist_ok=True)
    (paths.cache / "ingested.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def _compile_package(paths: TalamusPaths, package: NormalizedPackage, llm: LLMProvider) -> int:
    """Estrae le note dal pacchetto, le scrive e risolve i wikilink a lotto,
    ricostruisce gli indici."""
    paths.normalized.mkdir(parents=True, exist_ok=True)
    normalized_file = paths.normalized / Path(package.raw_path).name
    normalized_file.write_text(package.render(), encoding="utf-8")
    normalized_rel = normalized_file.relative_to(paths.project_root).as_posix()
    notes = extract_notes(package, llm, normalized_path=normalized_rel)
    # Fase 1: persisti tutti gli oggetti canonici, così l'intero lotto è noto.
    for note in notes:
        write_note_json(paths, note)
    # Fase 2: rendi il Markdown con un registro dell'INTERO lotto (+ note esistenti),
    # così i wikilink tra note dello stesso lotto si risolvono senza link rotti.
    registry = NoteRegistry.from_notes(load_notes(paths))
    for note in notes:
        render_note_markdown(paths, note, registry)
    rebuild_indexes(paths)
    return len(notes)


def ingest_file(paths: TalamusPaths, file_path: Path, llm: LLMProvider) -> dict:
    paths.ensure_directories()
    text = extract_text(file_path)
    raw_copy = paths.raw / file_path.name
    shutil.copyfile(file_path, raw_copy)
    package = normalize_text(raw_copy.as_posix(), text)
    written = _compile_package(paths, package, llm)
    hashes = _load_hashes(paths)
    hashes[file_path.name] = _content_hash(text)
    _save_hashes(paths, hashes)
    return {"notes_written": written, "source": file_path.name}


def ingest_url(paths: TalamusPaths, url: str, llm: LLMProvider) -> dict:
    paths.ensure_directories()
    text = read_url(url)
    raw_path = paths.raw / f"web-{_content_hash(text)[:8]}.md"
    raw_path.write_text(text, encoding="utf-8")
    package = normalize_text(raw_path.as_posix(), text)
    written = _compile_package(paths, package, llm)
    return {"notes_written": written, "source": url}


def ingest_dir(paths: TalamusPaths, directory: Path, llm: LLMProvider) -> dict:
    """Ingest every supported file in a folder (recursive); skip unchanged ones.

    Files that can't be read or compiled are collected in ``failed`` (name + reason)
    instead of being silently dropped, so the user sees what didn't make it in.
    """
    paths.ensure_directories()
    hashes = _load_hashes(paths)
    files = skipped = notes = 0
    failed: list[dict] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED:
            continue
        try:
            text = extract_text(path)
        except Exception as exc:  # unreadable source — record, don't abort the batch
            failed.append({"file": path.name, "error": str(exc)})
            continue
        if hashes.get(path.name) == _content_hash(text):
            skipped += 1
            continue
        try:
            written = ingest_file(paths, path, llm)
        except Exception as exc:  # extraction/compile failure — record and continue
            failed.append({"file": path.name, "error": str(exc)})
            continue
        files += 1
        notes += written["notes_written"]
    return {"files": files, "skipped": skipped, "notes_written": notes, "failed": failed}


def ingest_path(paths: TalamusPaths, target: str, llm: LLMProvider) -> dict:
    """Ingest a file, a folder (recursively), or a URL."""
    if is_url(target):
        return ingest_url(paths, target, llm)
    path = Path(target)
    if path.is_dir():
        return ingest_dir(paths, path, llm)
    return ingest_file(paths, path, llm)


def remember_session(paths: TalamusPaths, transcript: str, diff: str, llm: LLMProvider) -> dict:
    """Una sessione-agente (transcript + diff) diventa note, se supera il gate."""
    paths.ensure_directories()
    if not session_worth_remembering(transcript, diff):
        return {"skipped": True, "notes_written": 0}
    digest = hashlib.sha256((transcript + "\n" + diff).encode("utf-8")).hexdigest()[:8]
    raw_path = paths.raw / f"session-{digest}.md"
    raw_path.write_text(
        transcript + ("\n\n---\n\n" + diff if diff.strip() else ""), encoding="utf-8"
    )
    package = normalize_session(raw_path.as_posix(), transcript, diff)
    written = _compile_package(paths, package, llm)
    return {"skipped": False, "notes_written": written}


def ingest_text(paths: TalamusPaths, text: str, llm: LLMProvider, name: str = "insight") -> dict:
    """Ingerisce un frammento di testo (es. un'intuizione che l'agente vuole
    ricordare) come scheda."""
    paths.ensure_directories()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    raw_path = paths.raw / f"{name}-{digest}.md"
    raw_path.write_text(text, encoding="utf-8")
    package = normalize_text(raw_path.as_posix(), text)
    written = _compile_package(paths, package, llm)
    return {"notes_written": written}
