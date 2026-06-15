# State — what has been built, measured and rejected

The living ledger. Updated at every milestone (see governance in
[AGENTS.md](../AGENTS.md)). Numbers here are the canonical reference: do not
re-measure what is already here unless the code path changed.

## Current quality dashboard (book corpus, 243→212 notes, 42-case local eval)

| Metric | Value | Bar (PRODUCT.md) |
|---|---|---|
| Ask path hit-rate@8 | **0.972** (pre-consolidation brain; re-measure post-consolidation pending) | ≥ 0.95 ✓ |
| Search hit-rate@5 | **0.861** | ≥ 0.92 — gap 0.06 |
| Search MRR | 0.726 | — |
| direct / direct-en recall | 1.000 / 1.000 (MRR 0.958 / 1.000) | — |
| vague hit (search) | 0.750 | weakest front |
| Negative rejection (search level) | 0.000 — answer-level guard works instead | RS2.6 open |
| Search latency @ 10k | ~55 ms | ✓ |
| Routing tokens | 12× cheaper at 10k (tree) | ✓ |

Docs corpus (120 cases) floors in CI: recall ≥ 0.45, MRR ≥ 0.40, hit ≥ 0.55
(`tests/test_talamus_recall_floor.py`).

## Build history (each row = measured, committed, pushed)

| Phase | What shipped |
|---|---|
| Foundations (Kortex era) | Text loop: ingest → extraction → notes with provenance → graph + BM25 → cited answers; MCP read+write; session capture; ontology L1 |
| A0–A6 | Rebrand to Talamus; ruff+mypy+multi-OS CI; easy CLI; engine adapters; onboarding; README; mkdocs site |
| B1–B6 | Consolidation; IT stemmer + query expansion; domain induction + overview-routed ask; bitemporal history; source-correction; typed relations |
| C | PDF/HTML/DOCX/URL/folder ingest; Flet UI first cut; eval harness; reranking; token budget |
| M0 | Measurement baseline: real 120-case eval-set, corpora, bench (recall@5 0.41; 8.5 s @ 10k; routing tokens linear) |
| M1 | Multi-brain: registry, scope policies, federated pointer index, init scoping fix |
| M2 | Resumable jobs, review queue, progress |
| M3 | Repo scan: dry-run plan, gitignore, secret redaction, code digests |
| M4 | Persistent indexes (FTS5 + postings fallback): 8458 ms → 34 ms @ 10k (249×); ask --trace |
| M5 | Ontology Lab: evidence → clustering → 1-call naming → versioned schema → promotion rules (≥8 support, ≥3 notes) → runtime re-typing |
| M6 | Bitemporal: parse_when, append-only claims, ask/read --as-of |
| M7 | Active verify: provenance status, batch verify, corrections → review |
| M8–M11 | Dashboard CLI; UI workbench 11 views; MCP final; release hardening |
| Fase R | UI revolution (physics graph, inspector, full settings); codex/gemini adapters; `talamus setup`; hierarchical overview (areas) |
| RS1 (recall research) | **Trigram cognate bridge** (no embeddings): 3-channel index → recall +25%, MRR +35%, cross-source +76%; CI floors. Rejected with data: graph propagation (−2 pt), RRF, seed displacement |
| Language | Three-layer architecture (English prompts / user-language prose / English-canonical machine layer); validated e2e with real codex |
| Book test | 500-page real PDF: 58 chunks, ~33 min, 267 notes, resumable job, consent gate. Found+fixed 4 real bugs: self-links, stale running jobs, domain induction collapse at scale (→ batched), verify hashing wrong artifact (243/243 false stale → 0) |
| Engine speed | Model passthrough (`llm_model` → `-m`); gemini hardened (read-only + skip-trust); measured: flash-lite 16 s vs codex default 46 s per call |
| RS2 | Two-corpora law; book eval-set; **ask selection fix** (domain members ranked vs question + global escape seeds): ask hit 0.361 → 0.750; **`talamus enrich`** (symptom vocabulary, batched, consented): search hit 0.806 → 0.833, zero regressions; strict=False JSON salvage |
| RS3 | **LLM query expansion before routed selection** ("the LLM is the embedding model"): ask hit → **0.972**, vague 0.50 → 0.81; **consolidation** (20 reviewed groups, 31 notes merged): search hit → **0.861**, direct MRR → 1.0; merge_notes retrieval_text union fix; truncation-salvage parser; hostile-model CI battery + enrich guard-rails |
| RS4 | **Hub-note suppression** (mild length penalty LP=0.5, self-targeting): docs hit 0.600 → 0.618 (code/cross-source/direct up), book neutral; CACHE_VERSION 4. Two-corpora error analysis confirmed search's two failure classes: hub pollution (index-fixable, done) vs pure-semantic vague (needs ingest-time enrichment) |

## Rejected with data — do NOT redo without new evidence

| Hypothesis | Verdict |
|---|---|
| Graph score propagation in ranking | −2 pt recall (RS1) |
| Reciprocal-rank fusion | worse than weighted blend (RS1) |
| Ontology 1-hop expansion swapped for seeds | no lift, no-op at full limit (RS2.1) |
| Ontology triangulation (multi-hit convergence) | docs MRR −0.14, hub pollution (RS3) |
| Hyphen-split tokenization | trigram channel already bridges; docs slightly worse |
| PRF (pseudo-relevance feedback) | vague unchanged, MRR down on both corpora |
| Symptom directive inside the EXTRACTION prompt | lite models lose 12% coverage; enrichment must be the separate batched pass |
| Hard negative rejection at search level (3 designs) | distributions overlap; answer-level guard + soft signal is the route (RS2.6 open) |
| More global escape seeds (2→4) | dilutes; 2 is right |
| Trigram channel over symptom text | lexical already covers it |

## Open fronts (current queue)

1. Search hit 0.861 → ≥ 0.92: symptoms generated from note BODY (not just
   summary); remaining 5 vague/cross misses on the book corpus.
2. Ask re-measure on the post-consolidation brain (routing cache invalidated).
3. RS2.6: negative rejection as a SOFT coverage signal passed to ask.
4. RS2.5: extraction granularity vs model (lite models compress specifics).
5. RS-GEN: full e2e with ollama + small local model (the zero-subscription
   promise) — ollama installed on the dev machine, no model pulled yet.
6. RS-GEN: third corpus, different domain, anti-overfitting.
7. 100k-note bench; UI visual verdict from the maintainer; clean-venv install
   checklist.

## Live artifacts (not in repo)

- `C:/dev/_talamus_book` — the book brain (212 notes, enriched+consolidated,
  registered). Its eval-set `eval-cases-book.json` stays local (copyright).
- `C:/dev/_talamus_book2` — symptom-prompt A/B brain (unregistered, kept for
  comparison).
- `C:/dev/Talamus_docs_archive` — superseded specs/plans (history also in git).
