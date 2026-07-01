from __future__ import annotations

import dataclasses
import tempfile
import time
from pathlib import Path

from benchmarks.shootout.systems.base import Doc, IngestStats
from talamus.adapters.llm import LLMProvider
from talamus.indexes import search_index
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.smartsearch import expand_query
from talamus.store import overwrite_note_json, rebuild_indexes


def _note_for(note_id: str, doc: Doc) -> CanonicalNote:
    src = SourceRef("raw/bench.md", "raw/bench.md#1", "bench", "sha256:x", [doc.text])
    return dataclasses.replace(
        CanonicalNote.minimal(doc.title or note_id, sources=[src]),
        note_id=note_id,
        retrieval_text=f"{doc.title} {doc.text}",
        summary=doc.text[:200],
    )


class _TalamusBase:
    name = "talamus"

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._paths = TalamusPaths(Path(self._tmp.name))
        self._paths.ensure_directories()
        # map by note_id (which search_index returns), robust to empty/duplicate titles
        self._noteid_to_docid: dict[str, str] = {}

    def ingest(self, docs: list[Doc]) -> IngestStats:
        start = time.perf_counter()
        for i, doc in enumerate(docs):
            note_id = f"bench-{i:06d}"
            self._noteid_to_docid[note_id] = doc.doc_id
            overwrite_note_json(self._paths, _note_for(note_id, doc))
        rebuild_indexes(self._paths)
        index_bytes = sum(p.stat().st_size for p in self._paths.cache.rglob("*") if p.is_file())
        return IngestStats(seconds=time.perf_counter() - start, index_bytes=index_bytes)

    def _search(self, query: str, k: int) -> list[str]:
        hits = search_index(self._paths, query, limit=k)
        return [self._noteid_to_docid.get(h["note_id"], h["note_id"]) for h in hits]


class TalamusSearch(_TalamusBase):
    name = "talamus-search"

    def query(self, q: str, k: int) -> list[str]:
        return self._search(q, k)


class TalamusSmart(_TalamusBase):
    name = "talamus-smart"

    def __init__(self, llm: LLMProvider) -> None:
        super().__init__()
        self._llm = llm

    def query(self, q: str, k: int) -> list[str]:
        return self._search(expand_query(self._paths, q, StaticRouter(self._llm)), k)
