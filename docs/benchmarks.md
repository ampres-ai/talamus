# Benchmarks — the one-screen proof

Every number below traces to a committed artifact in `benchmarks/results/`
(or to the canonical ledger `dev/STATE.md`), and the whole screen re-renders
with one free command:

```bash
python benchmarks/run.py --tier one-screen
```

| claim | number | vs competitors | source artifact |
| --- | --- | --- | --- |
| Tokens per answer | -97.7% vs loading the brain into context | load-all grows linearly and hits the context wall | dev/STATE.md (RS5 profiler row) |
| Answers cited & source-resolvable | 100% | no competitor here has a provenance model | dev/STATE.md (RS5 profiler row) |
| Marginal cost per answer | EUR 0 (the LLM you already have) | dense RAG pays embedding infrastructure per corpus | dev/STATE.md (RS5 profiler row) |
| Cross-language + vague retrieval (book, hit@10) | talamus-smart 0.971 (recall 0.886) | BM25 0.829 - MiniLM vector DB 0.743 | benchmarks/results/2026-06-17-shootout-book.json |
| THE HONEST LOSS: strong dense ranking (book) | multilingual-e5 nDCG 0.837 / MRR 0.857 | talamus-smart 0.783 / 0.796 (we keep best hit/recall) | benchmarks/results/2026-06-17-shootout-book.json |
| English-only turf (SciFact, after the adaptive-trigram fix) | talamus-search nDCG 0.664 / recall 0.797 | BM25 0.652 / 0.776 - MiniLM 0.645 / 0.783 | dev/STATE.md (RS8 row; pre-fix baseline benchmarks/results/2026-06-15-shootout-scifact.json) |
| Answer quality end-to-end (judged, book) | context hit 0.943 / correctness 0.914 | BM25 0.771/0.871 - vector DB 0.657/0.757 | benchmarks/results/2026-06-17-ask-eval.json |
| The ontology improves ANSWERS (same brain, ON vs OFF) | ON: hit 1.000 / correct 0.957 | OFF: 0.857 / 0.886 | benchmarks/results/2026-06-17-ask-ablation.json |
| Fully local, EUR 0 (ollama gemma as generator AND judge) | correctness 0.800 | 0.857 with a cloud engine — a small, stated gap | benchmarks/results/2026-06-17-ask-eval-ollama.json |
| Honest refusal on out-of-scope questions | 1.000 | every competitor <= 0.833 | benchmarks/results/2026-06-17-ask-eval.json |
| Search latency | p95 72.6 ms @10k - p50 624.4 ms @100k | no LLM call on the search path | benchmarks/results/2026-07-02-scale-100k.json |

The honest read: on cross-language and vague queries (a real bilingual book
corpus) Talamus beats BM25 and a MiniLM vector DB with zero embedding
infrastructure, and its end-to-end judged answers lead every competitor while
refusing cleanly on questions the brain cannot answer. It does NOT win
everything: a strong multilingual dense model (multilingual-e5) ranks better
(nDCG/MRR) on that same corpus, and that row stays on this screen on purpose.
The trade Talamus offers is different: the semantic power comes from the LLM
you already have, so answers cost EUR 0 marginal, burn ~98% fewer tokens than
loading the corpus into context, and every answer cites sources you can open —
plus the time (as-of) and self-emerging-ontology moats no retrieval stack here
has. Reproduce it: every row's artifact is committed, with the command that
generated it in its sibling .md report.

## Reproducing the underlying runs

The one-screen tier only assembles committed results. The measuring runs
themselves (paid: real competitors + LLM expansion) are:

```bash
python benchmarks/run.py --tier shootout --yes --dataset scifact   # dense turf (public BEIR)
python benchmarks/run.py --tier shootout --yes --dataset book      # our turf (needs a local brain)
python benchmarks/ask_eval/run.py --queries 0                      # judged answers (local brain + ollama judge)
```

The book corpus is a real 500-page copyrighted book compiled into a local
brain, so that brain and its eval-set stay on the maintainer's machine — the
committed artifacts carry the numbers, the SciFact run is fully public.

Each artifact's sibling `.md` report records the exact provenance (git
commit, engine, dataset) of its run.
