"""Adapt a BEIR dataset into our JudgedCorpus. Network access is isolated in
load_beir; beir_to_corpus is pure and unit-tested."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JudgedCorpus:
    docs: list[tuple[str, str, str]]  # (doc_id, title, text)
    queries: dict[str, str]  # query_id -> text
    qrels: dict[str, dict[str, int]]  # query_id -> {doc_id: grade}

    @property
    def n_docs(self) -> int:
        return len(self.docs)

    def as_docs(self) -> list:
        from benchmarks.shootout.systems.base import Doc  # late import: stay dep-free

        return [Doc(doc_id, title, text) for doc_id, title, text in self.docs]


def beir_to_corpus(
    corpus: dict[str, dict], queries: dict[str, str], qrels: dict[str, dict[str, int]]
) -> JudgedCorpus:
    """Pure adapter from BEIR's in-memory shape to JudgedCorpus. Drops queries
    that have no relevance judgments (they cannot be scored)."""
    judged_q = {qid: text for qid, text in queries.items() if qrels.get(qid)}
    docs = [(doc_id, d.get("title", ""), d.get("text", "")) for doc_id, d in corpus.items()]
    return JudgedCorpus(docs=docs, queries=judged_q, qrels={q: qrels[q] for q in judged_q})


def load_beir(name: str = "scifact", data_root: str = ".bench-data") -> JudgedCorpus:
    """Download (once) and load a BEIR dataset as a JudgedCorpus. Manual tier."""
    from beir import util
    from beir.datasets.data_loader import GenericDataLoader

    root = Path(data_root)
    data_path = root / name
    if not data_path.is_dir():
        url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{name}.zip"
        util.download_and_unzip(url, str(root))
    corpus, queries, qrels = GenericDataLoader(data_folder=str(data_path)).load(split="test")
    return beir_to_corpus(corpus, queries, qrels)
