# Benchmarks (dev-only)

Reproducible measurements that back Talamus's claims. NOT part of the package —
competitor deps (`rank-bm25`, `beir`, and later embeddings/mem0) live here so the
product stays embedding-free. Needs the `bench` extra.

```bash
pip install -e ".[bench]"
```

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

The design spec and full implementation plan live locally under `.superpowers/`
(not committed).
