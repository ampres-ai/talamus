from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Doc:
    """One corpus document, identical across every system under test."""

    doc_id: str
    title: str
    text: str


@dataclass
class IngestStats:
    """What ingesting the corpus cost a system. Tokens are the universal currency;
    everything is comparable because every system gets the same corpus."""

    seconds: float = 0.0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    index_bytes: int = 0
    peak_ram_bytes: int = 0


class RetrievalSystem(Protocol):
    """The only contract a competitor must satisfy. Add a rival = one new file."""

    name: str

    def ingest(self, docs: list[Doc]) -> IngestStats: ...

    def query(self, q: str, k: int) -> list[str]:
        """Return up to k doc_ids, best first."""
        ...
