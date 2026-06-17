"""The honest steelman: a STRONG multilingual embedding model, not the
English-centric MiniLM. If Talamus holds against this on MIRACL + book, the
cross-language claim is bulletproof; if it loses, we learn the real gap and
report it. Bench-only; runs locally on CPU.

multilingual-e5 requires `query: ` / `passage: ` prefixes for correct retrieval
(the model was trained with them); omitting them silently degrades recall."""

from __future__ import annotations

from benchmarks.shootout.systems.base import Doc
from benchmarks.shootout.systems.vectordb_system import VectorDBSystem


def e5_query_text(q: str) -> str:
    return f"query: {q}"


def e5_passage_text(title: str, text: str) -> str:
    return f"passage: {title} {text}".strip()


class MultilingualDenseSystem(VectorDBSystem):
    """multilingual-e5 with the required query/passage prefixes."""

    name = "dense-multilingual"

    def __init__(self, model_name: str = "intfloat/multilingual-e5-base") -> None:
        super().__init__(model_name=model_name)

    def ingest(self, docs: list[Doc]):
        prefixed = [Doc(d.doc_id, "", e5_passage_text(d.title, d.text)) for d in docs]
        return super().ingest(prefixed)

    def query(self, q: str, k: int) -> list[str]:
        return super().query(e5_query_text(q), k)
