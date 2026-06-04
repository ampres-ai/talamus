from __future__ import annotations

import shutil
from pathlib import Path

from kortex.adapters.llm import LLMProvider
from kortex.extract import extract_notes
from kortex.linking import NoteRegistry
from kortex.normalize import normalize_text
from kortex.paths import KortexPaths
from kortex.store import load_notes, rebuild_indexes, render_note_markdown, write_note_json


def ingest_file(paths: KortexPaths, file_path: Path, llm: LLMProvider) -> dict:
    paths.ensure_directories()
    text = file_path.read_text(encoding="utf-8")

    raw_copy = paths.raw / file_path.name
    shutil.copyfile(file_path, raw_copy)

    package = normalize_text(raw_copy.as_posix(), text)
    notes = extract_notes(package, llm)
    # Fase 1: persisti tutti gli oggetti canonici, così l'intero lotto è noto.
    for note in notes:
        write_note_json(paths, note)
    # Fase 2: rendi il Markdown con un registro dell'INTERO lotto (+ note esistenti),
    # così i wikilink tra note dello stesso lotto si risolvono senza link rotti.
    registry = NoteRegistry.from_notes(load_notes(paths))
    for note in notes:
        render_note_markdown(paths, note, registry)
    rebuild_indexes(paths)
    return {"notes_written": len(notes), "source": file_path.name}
