"""MIRACL multilingual judged loader. The HF dataset carries positive and
negative passages inline per query, so we build a self-contained pooled corpus
(positives + official hard negatives) — tractable on one machine and honest
(it is MIRACL's own pool). Italian dev split is the cross-language target;
MIRACL test qrels are hidden (it is a competition)."""

from __future__ import annotations

from benchmarks.shootout.corpora.judged import JudgedCorpus


def miracl_rows_to_corpus(rows: list[dict]) -> JudgedCorpus:
    """Pure adapter from MIRACL HF rows to JudgedCorpus (unit-tested, no network).

    Each row: {query_id, query, positive_passages[], negative_passages[]} where a
    passage is {docid, title, text}. Positives become qrels; positives+negatives
    form the retrieval pool."""
    docs: dict[str, tuple[str, str, str]] = {}
    queries: dict[str, str] = {}
    qrels: dict[str, dict[str, int]] = {}
    for row in rows:
        qid = str(row["query_id"])
        queries[qid] = row["query"]
        rels: dict[str, int] = {}
        for passage in row.get("positive_passages", []):
            did = str(passage["docid"])
            docs[did] = (did, passage.get("title", ""), passage.get("text", ""))
            rels[did] = 1
        for passage in row.get("negative_passages", []):
            did = str(passage["docid"])
            docs[did] = (did, passage.get("title", ""), passage.get("text", ""))
        if rels:
            qrels[qid] = rels
    judged = {q: queries[q] for q in qrels}
    return JudgedCorpus(docs=list(docs.values()), queries=judged, qrels=qrels)


def load_miracl(lang: str = "it", split: str = "dev", limit: int | None = None) -> JudgedCorpus:
    """Download (once) and load a MIRACL language split as a pooled JudgedCorpus.

    Needs `datasets` (in the [bench] extra) and may require `huggingface-cli
    login` if the dataset is gated."""
    from datasets import load_dataset

    ds = load_dataset("miracl/miracl", lang, split=split)
    rows = list(ds)[:limit] if limit else list(ds)
    return miracl_rows_to_corpus(rows)
