from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from talamus.errors import EngineFailed, EngineNotFound
from talamus.extract import extract_notes
from talamus.linking import NoteRegistry
from talamus.normalize import NormalizedPackage, normalize_text
from talamus.paths import TalamusPaths
from talamus.routing import Router, TaskClass
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


def _compile_package(
    paths: TalamusPaths,
    package: NormalizedPackage,
    router: Router,
    preamble: str = "",
    reindex: bool = True,
    task: TaskClass = TaskClass.EXTRACTION,
) -> int:
    """Extract the notes from the package, write them, resolve wikilinks in batch,
    and rebuild the indexes."""
    from talamus.config import load_or_default, resolve_language

    paths.normalized.mkdir(parents=True, exist_ok=True)
    normalized_file = paths.normalized / Path(package.raw_path).name
    normalized_file.write_text(package.render(), encoding="utf-8")
    normalized_rel = normalized_file.relative_to(paths.project_root).as_posix()
    language = resolve_language(load_or_default(paths.config_path))
    notes = extract_notes(
        package,
        router,
        normalized_path=normalized_rel,
        preamble=preamble,
        language=language,
        task=task,
    )
    # Phase 1: persist every canonical object, so the whole batch is known.
    for note in notes:
        write_note_json(paths, note)
    # Phase 2: render the Markdown with a registry of the WHOLE batch (+ existing
    # notes), so wikilinks between same-batch notes resolve without broken links.
    registry = NoteRegistry.from_notes(load_notes(paths))
    for note in notes:
        render_note_markdown(paths, note, registry)
    if reindex:
        rebuild_indexes(paths)
    return len(notes)


CHUNK_CHARS = 20_000  # ~5k tokens per extraction call: bigger documents are chunked
CHUNK_OVERLAP = 1_000  # ~250 tokens of deterministic context from the prior chunk


def _base_split_chunks(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in text.split("\n\n"):
        block = paragraph + "\n\n"
        if size + len(block) > limit and current:
            chunks.append("".join(current).strip())
            current, size = [], 0
        while len(block) > limit:  # a single paragraph larger than the limit
            chunks.append(block[:limit].strip())
            block = block[limit:]
        current.append(block)
        size += len(block)
    if current and "".join(current).strip():
        chunks.append("".join(current).strip())
    return chunks


def _overlap_tail(chunk: str, overlap: int) -> str:
    if overlap <= 0 or not chunk:
        return ""
    paragraphs = chunk.split("\n\n")
    tail: list[str] = []
    size = 0
    for paragraph in reversed(paragraphs):
        addition = len(paragraph) if not tail else len(paragraph) + 2
        if not tail and len(paragraph) > overlap:
            return paragraph[-overlap:]
        if size + addition > overlap:
            break
        tail.append(paragraph)
        size += addition
    tail.reverse()
    return "\n\n".join(tail)


def split_chunks(text: str, limit: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split big documents at paragraph boundaries with deterministic overlap.

    ``limit`` applies to each chunk's own content. Every chunk after the first is
    prefixed with the tail of the previous base chunk, so its total size may
    exceed ``limit`` by up to ``overlap + 2`` characters. This headroom is
    intentional: the limit guards LLM call size and the overlap window preserves
    boundary concepts for extraction.

    Deterministic: the same text always yields the same chunks (resume relies on it).
    ``overlap=0`` reproduces the historical chunk output exactly.
    """
    chunks = _base_split_chunks(text, limit)
    if overlap <= 0 or len(chunks) == 1:
        return chunks
    overlapped = [chunks[0]]
    for previous, chunk in zip(chunks, chunks[1:], strict=False):
        tail = _overlap_tail(previous, overlap)
        overlapped.append(f"{tail}\n\n{chunk}" if tail else chunk)
    return overlapped


def estimate_chunks(paths: TalamusPaths, file_path: Path) -> dict:
    """Cost preview for a big-document ingest: chunks = LLM calls. No LLM, no writes."""
    text = extract_text(file_path)
    chunks = split_chunks(text)
    return {
        "source": file_path.name,
        "chars": len(text),
        "chunks": len(chunks),
        "est_llm_calls": len(chunks),
        "est_input_tokens": len(text) // 4,
    }


def ingest_file(paths: TalamusPaths, file_path: Path, router: Router) -> dict:
    paths.ensure_directories()
    text = extract_text(file_path)
    raw_copy = paths.raw / file_path.name
    shutil.copyfile(file_path, raw_copy)
    chunks = split_chunks(text)
    if len(chunks) == 1:
        package = normalize_text(raw_copy.as_posix(), text)
        written = _compile_package(paths, package, router)
        hashes = _load_hashes(paths)
        hashes[file_path.name] = _content_hash(text)
        _save_hashes(paths, hashes)
        return {"notes_written": written, "source": file_path.name}
    return ingest_large(paths, file_path, router)


def ingest_large(paths: TalamusPaths, file_path: Path, router: Router, job_record=None) -> dict:
    """Big-document ingest as a persistent, resumable job: one extraction call per
    chunk, progress saved after each — a 500-page book survives crashes and
    interruptions, and `talamus jobs resume` picks up exactly where it stopped."""
    from talamus.jobs import JobStore, run_items

    paths.ensure_directories()
    text = extract_text(file_path)
    raw_copy = paths.raw / file_path.name
    if file_path.resolve() != raw_copy.resolve():
        shutil.copyfile(file_path, raw_copy)
    chunks = split_chunks(text)
    store = JobStore(paths)
    record = job_record or store.create(
        "ingest", payload={"file": str(file_path), "chunks": len(chunks)}
    )
    notes_total = 0
    failed: list[dict] = []

    def handle(item: str) -> None:
        nonlocal notes_total
        index = int(item.split("-")[1])
        # always .md: the chunk is extracted text, never the original binary
        chunk_raw = paths.raw / f"{file_path.stem}-c{index:03d}.md"
        chunk_raw.write_text(chunks[index], encoding="utf-8")
        package = normalize_text(chunk_raw.as_posix(), chunks[index])
        for attempt in (1, 2):
            try:
                # no reindex per chunk: a book would do N rebuilds on a growing
                # brain — rebuild ONCE at the end of the job (even on a crash)
                notes_total += _compile_package(paths, package, router, reindex=False)
                return
            except (EngineFailed, EngineNotFound):
                raise  # engine down: the job stops resumably, the chunks are not burned
            except Exception as exc:  # content error (e.g. malformed JSON)
                if attempt == 1:  # the model is nondeterministic: one retry almost always works
                    store.log(record.job_id, f"chunk {index}: retry after {exc}")
                    continue
                failed.append({"chunk": index, "error": str(exc)})
                store.log(record.job_id, f"chunk {index}: FAILED {exc}")

    items = [f"chunk-{i:03d}" for i in range(len(chunks))]
    try:
        final = run_items(store, record, items, handle, stage="ingest")
    finally:
        rebuild_indexes(paths)  # notes already written stay searchable even after a crash
    hashes = _load_hashes(paths)
    hashes[file_path.name] = _content_hash(text)
    _save_hashes(paths, hashes)
    final.result = {"notes_written": notes_total, "failed": failed, "chunks": len(chunks)}
    store.save(final)
    return {
        "notes_written": notes_total,
        "source": file_path.name,
        "chunks": len(chunks),
        "job_id": final.job_id,
        "state": final.state,
        "failed": failed,
    }


def ingest_url(paths: TalamusPaths, url: str, router: Router) -> dict:
    paths.ensure_directories()
    text = read_url(url)
    raw_path = paths.raw / f"web-{_content_hash(text)[:8]}.md"
    raw_path.write_text(text, encoding="utf-8")
    package = normalize_text(raw_path.as_posix(), text)
    written = _compile_package(paths, package, router)
    return {"notes_written": written, "source": url}


def ingest_dir(paths: TalamusPaths, directory: Path, router: Router) -> dict:
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
            written = ingest_file(paths, path, router)
        except Exception as exc:  # extraction/compile failure — record and continue
            failed.append({"file": path.name, "error": str(exc)})
            continue
        files += 1
        notes += written["notes_written"]
    return {"files": files, "skipped": skipped, "notes_written": notes, "failed": failed}


def ingest_path(paths: TalamusPaths, target: str, router: Router) -> dict:
    """Ingest a file, a folder (recursively), or a URL."""
    if is_url(target):
        return ingest_url(paths, target, router)
    path = Path(target)
    if path.is_dir():
        return ingest_dir(paths, path, router)
    return ingest_file(paths, path, router)


def _log_capture(paths: TalamusPaths, decision: str, detail: str) -> None:
    """Append the capture decision to .talamus/logs/capture.log (F10.5):
    every remember/skip is auditable, with its reason."""
    import time

    paths.logs.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with (paths.logs / "capture.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {decision} {detail}\n")


def remember_session(paths: TalamusPaths, transcript: str, diff: str, router: Router) -> dict:
    """An agent session (transcript + diff) becomes notes, if it passes the gate."""
    paths.ensure_directories()
    if not session_worth_remembering(transcript, diff):
        _log_capture(
            paths,
            "skip",
            f"below the gate (transcript {len(transcript)} chars, diff {len(diff)} chars)",
        )
        return {"skipped": True, "notes_written": 0, "reason": "below worth-remembering gate"}
    digest = hashlib.sha256((transcript + "\n" + diff).encode("utf-8")).hexdigest()[:8]
    raw_path = paths.raw / f"session-{digest}.md"
    raw_path.write_text(
        transcript + ("\n\n---\n\n" + diff if diff.strip() else ""), encoding="utf-8"
    )
    package = normalize_session(raw_path.as_posix(), transcript, diff)
    written = _compile_package(paths, package, router, task=TaskClass.SESSION_REMEMBER)
    _log_capture(paths, "capture", f"session-{digest}: {written} notes")
    return {"skipped": False, "notes_written": written}


def ingest_text(
    paths: TalamusPaths,
    text: str,
    router: Router,
    name: str = "insight",
    preamble: str = "",
) -> dict:
    """Ingest a snippet of text (e.g. an insight the agent wants to remember) as a
    note. ``preamble`` adds instructions to the extractor (used by scan for the
    code digest)."""
    paths.ensure_directories()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    raw_path = paths.raw / f"{name}-{digest}.md"
    raw_path.write_text(text, encoding="utf-8")
    package = normalize_text(raw_path.as_posix(), text)
    written = _compile_package(paths, package, router, preamble=preamble)
    return {"notes_written": written}
