from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from talamus.adapters.llm import LLMProvider
from talamus.errors import EngineFailed, EngineNotFound
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


def _compile_package(
    paths: TalamusPaths,
    package: NormalizedPackage,
    llm: LLMProvider,
    preamble: str = "",
    reindex: bool = True,
) -> int:
    """Estrae le note dal pacchetto, le scrive e risolve i wikilink a lotto,
    ricostruisce gli indici."""
    from talamus.config import load_or_default, resolve_language

    paths.normalized.mkdir(parents=True, exist_ok=True)
    normalized_file = paths.normalized / Path(package.raw_path).name
    normalized_file.write_text(package.render(), encoding="utf-8")
    normalized_rel = normalized_file.relative_to(paths.project_root).as_posix()
    language = resolve_language(load_or_default(paths.config_path))
    notes = extract_notes(
        package, llm, normalized_path=normalized_rel, preamble=preamble, language=language
    )
    # Fase 1: persisti tutti gli oggetti canonici, così l'intero lotto è noto.
    for note in notes:
        write_note_json(paths, note)
    # Fase 2: rendi il Markdown con un registro dell'INTERO lotto (+ note esistenti),
    # così i wikilink tra note dello stesso lotto si risolvono senza link rotti.
    registry = NoteRegistry.from_notes(load_notes(paths))
    for note in notes:
        render_note_markdown(paths, note, registry)
    if reindex:
        rebuild_indexes(paths)
    return len(notes)


CHUNK_CHARS = 20_000  # ~5k token per chiamata di estrazione: documenti più grandi vanno a chunk


def split_chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Split big documents at paragraph boundaries, each chunk under ``limit``.

    Deterministic: the same text always yields the same chunks (resume relies on it)."""
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


def ingest_file(paths: TalamusPaths, file_path: Path, llm: LLMProvider) -> dict:
    paths.ensure_directories()
    text = extract_text(file_path)
    raw_copy = paths.raw / file_path.name
    shutil.copyfile(file_path, raw_copy)
    chunks = split_chunks(text)
    if len(chunks) == 1:
        package = normalize_text(raw_copy.as_posix(), text)
        written = _compile_package(paths, package, llm)
        hashes = _load_hashes(paths)
        hashes[file_path.name] = _content_hash(text)
        _save_hashes(paths, hashes)
        return {"notes_written": written, "source": file_path.name}
    return ingest_large(paths, file_path, llm)


def ingest_large(paths: TalamusPaths, file_path: Path, llm: LLMProvider, job_record=None) -> dict:
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
        # sempre .md: il chunk è testo estratto, mai il binario originale
        chunk_raw = paths.raw / f"{file_path.stem}-c{index:03d}.md"
        chunk_raw.write_text(chunks[index], encoding="utf-8")
        package = normalize_text(chunk_raw.as_posix(), chunks[index])
        for attempt in (1, 2):
            try:
                # niente reindex per chunk: un libro farebbe N rebuild su un brain
                # che cresce — si ricostruisce UNA volta a fine job (anche su crash)
                notes_total += _compile_package(paths, package, llm, reindex=False)
                return
            except (EngineFailed, EngineNotFound):
                raise  # motore giù: il job si ferma resumabile, non si bruciano i chunk
            except Exception as exc:  # errore di contenuto (es. JSON malformato)
                if attempt == 1:  # il modello è nondeterministico: un retry quasi sempre basta
                    store.log(record.job_id, f"chunk {index}: retry dopo {exc}")
                    continue
                failed.append({"chunk": index, "error": str(exc)})
                store.log(record.job_id, f"chunk {index}: FAILED {exc}")

    items = [f"chunk-{i:03d}" for i in range(len(chunks))]
    try:
        final = run_items(store, record, items, handle, stage="ingest")
    finally:
        rebuild_indexes(paths)  # le note già scritte restano cercabili anche dopo un crash
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


def _log_capture(paths: TalamusPaths, decision: str, detail: str) -> None:
    """Append the capture decision to .talamus/logs/capture.log (F10.5):
    every remember/skip is auditable, with its reason."""
    import time

    paths.logs.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with (paths.logs / "capture.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {decision} {detail}\n")


def remember_session(paths: TalamusPaths, transcript: str, diff: str, llm: LLMProvider) -> dict:
    """Una sessione-agente (transcript + diff) diventa note, se supera il gate."""
    paths.ensure_directories()
    if not session_worth_remembering(transcript, diff):
        _log_capture(
            paths,
            "skip",
            f"sotto la soglia del gate (transcript {len(transcript)} char, diff {len(diff)} char)",
        )
        return {"skipped": True, "notes_written": 0, "reason": "below worth-remembering gate"}
    digest = hashlib.sha256((transcript + "\n" + diff).encode("utf-8")).hexdigest()[:8]
    raw_path = paths.raw / f"session-{digest}.md"
    raw_path.write_text(
        transcript + ("\n\n---\n\n" + diff if diff.strip() else ""), encoding="utf-8"
    )
    package = normalize_session(raw_path.as_posix(), transcript, diff)
    written = _compile_package(paths, package, llm)
    _log_capture(paths, "capture", f"session-{digest}: {written} schede")
    return {"skipped": False, "notes_written": written}


def ingest_text(
    paths: TalamusPaths,
    text: str,
    llm: LLMProvider,
    name: str = "insight",
    preamble: str = "",
) -> dict:
    """Ingerisce un frammento di testo (es. un'intuizione che l'agente vuole
    ricordare) come scheda. ``preamble`` aggiunge istruzioni all'estrattore
    (usato dallo scan per il digest di codice)."""
    paths.ensure_directories()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    raw_path = paths.raw / f"{name}-{digest}.md"
    raw_path.write_text(text, encoding="utf-8")
    package = normalize_text(raw_path.as_posix(), text)
    written = _compile_package(paths, package, llm, preamble=preamble)
    return {"notes_written": written}
