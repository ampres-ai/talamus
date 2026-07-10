# Benchmarks

Reproducible measurements that back Talamus's claims. NOT part of the package —
competitor deps (`rank-bm25`, `beir`, and later embeddings/mem0) live here so the
product stays embedding-free. Needs the `bench` extra.

```bash
pip install -e ".[bench]"
```

## Tiers

Two speeds, so quality is guarded on every change without slowing the gate:

- **FAST** — runs inside `python dev.py` in seconds, no network/LLM. Recall floors
  guard retrieval quality on every change:
  - `tests/test_talamus_recall_floor.py` — the docs corpus (Talamus's own docs).
  - `tests/test_talamus_recall_floor_garden.py` — the **garden** corpus: six
    unrelated domains (cooking, astronomy, law, history, biology, personal finance),
    so a change must keep working across domains, not just on the repo's docs.
  - Measured 2026-06-24: both floors run in **~2.8 s** combined.
- **HEAVY** — opt in with `TALAMUS_BENCH_HEAVY=1` (download / LLM / scale); never in
  the normal gate. Includes BEIR, mem0, vectordb, the adaptive floor, and
  `tests/test_benchmarks_garden_enrich.py` (the real extract→enrich→ontology pipeline
  on the garden corpus with a local model). The shootout below is also heavy.

## Retrieval shootout

Head-to-head against competitors on the same judged corpus:

```bash
python benchmarks/run.py --tier ci                 # deterministic, free, every push
python benchmarks/run.py --tier shootout --yes     # real competitors + LLM (paid)
```

Results land in `benchmarks/results/` (JSON + Markdown, provenance-stamped).
Each system is an adapter behind one `RetrievalSystem` protocol
(`shootout/systems/`); add a rival = one new file.

## Token efficiency

- **`token_efficiency.py`** — token cost of targeted *recall* vs *loading the whole
  brain*, plus the cost of *search* (titles+summaries). Uses tiktoken (cl100k_base)
  as a tokenizer proxy. Build a brain first with `talamus ingest`.
