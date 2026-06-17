# State — what has been built, measured and rejected

The living ledger. Updated at every milestone (see governance in
[AGENTS.md](../AGENTS.md)). Numbers here are the canonical reference: do not
re-measure what is already here unless the code path changed.

## Current quality dashboard (book corpus, 243→212 notes, 42-case local eval)

| Metric | Value | Bar (PRODUCT.md) |
|---|---|---|
| Ask path hit-rate@8 | **0.972** (pre-consolidation brain; re-measure post-consolidation pending) | ≥ 0.95 ✓ |
| Search hit-rate@5 (plain) | **0.861** | lexical ceiling ~0.86–0.89 |
| Search hit-rate@5 (`--smart`, Query2doc) | **0.972** book / **0.782** docs | ≥ 0.92 ✓ (book) |
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
| RS4 | **Hub-note suppression** (length penalty LP=0.5, self-targeting): docs hit 0.600 → 0.618, book neutral; CACHE_VERSION 4. **Symptoms from body** (not summary): neutral-to-better, lifts vague-en. **THE SEARCH CEILING** (research/2026-06-rs4): symptom generation is nondeterministic and symptom bloat self-pollutes (union x2 0.889 > x3 0.833) → lexical+trigram search plateaus ~0.86–0.89 on a curated brain |
| RS3-lit | **Literature review** (doc2query, Query2doc, RM3, SDM/proximity, SPLADE): mapped every no-embedding lever to Talamus. Rejected with data: field separation (BM25F) doesn't transfer to small brains; proximity/coverage fails two-corpora (helps book, hurts docs). **THE WIN: Query2doc on search** — `talamus search --smart` expands the query with the user's LLM (cached) before searching: **book hit 0.861 → 0.972, docs 0.618 → 0.782**, vague 0.62 → 1.00. Wins on BOTH corpora; breaks the lexical ceiling; ≥0.92 bar met. The "LLM is the embedding model" thesis, literature-grounded and now on search, not just ask |
| Benchmark suite Ph1 + RS5 | **Competitive shootout harness** shipped (`benchmarks/`, dev-only, deps never in product): RetrievalSystem protocol + adapters (talamus-search/-smart, bm25, vectordb=MiniLM+FAISS, mem0=ollama), metrics, BEIR lite loader + corpus_from_brain, Layer-2 profiler, capability matrix, scale curves, tiered `run.py`, CI fakes (heavy tests gated by TALAMUS_BENCH_HEAVY). **TWO-FACES RESULT, both measured**: SciFact 300q (English, dense's turf) talamus-search recall@10 **0.776**/hit 0.793 ≈ vectordb 0.783/0.793 — **lexical TIES dense with ZERO embedding infra**; BOOK 35q (cross-language/vague, our turf) talamus-smart **0.886**/hit **0.971**, talamus-search 0.829/0.914, bm25 0.771/0.829, **vectordb LAST 0.700/0.743**. Profiler (book): token recall −97.7% vs load-all, verifiability **100%**, €0 marginal. Capability matrix: competitors ✗ on time/meaning/verifiability. mem0: ~48-53s/doc local, no doc-identity → not an IR competitor (matrix only). Honest: talamus-search < BM25 on nDCG/MRR monolingual (adaptive-trigram front). Report: dev/research/2026-06-rs5-competitive-shootout.md. Merged to main via feat/benchmarks-final |
| RS6 (answer quality) | **First end-to-end ASK answer-quality eval** (`benchmarks/ask_eval/`, book: 35q + 6 neg; generator gemini-flash-lite held constant; primary judge local `gemma4:e4b` `think=False`; claude cross-check). **talamus-smart leads**: context_hit **0.943**, correctness **0.914**, refusal 1.000; talamus-search 0.829/0.857/1.000; bm25 0.771/0.871/0.833; vectordb 0.657/0.757/0.833. Inter-judge agreement gemma↔claude **1.00/1.00** (n=12) → local €0 judge credible, not flattering. **Ontology ON/OFF ablation (real ask): ON lifts context_hit 0.857→1.000 and correctness 0.886→0.957** — the emergent ontology improves ANSWERS, not just navigation (the MEANING moat, measured). Found+fixed: `gemma4:e4b` is a reasoning model → `think=False` mandatory else empty verdicts silently score 0.000; generator speed measured (gemini-flash-lite fastest, codex-cli unavailable). Honest: faithfulness saturates ~1.0 (shared faithful generator, so it measures the generator not retrieval); refusal delta = 1 question on 6 negatives (noise); ablation faithfulness judged vs gold docs = artifact (fix queued). Report: dev/research/2026-06-rs6-answer-quality.md. Branch feat/rs6-benchmark-round (not merged) |
| RS7 (competitive expansion) | **Honest steelman**: added a STRONG multilingual dense model (multilingual-e5). On the book it is competitive/better — e5 nDCG **0.837** / MRR **0.857** (LEADS, above talamus-smart 0.783/0.796), recall 0.871; talamus-smart keeps best hit 0.971 / recall 0.886; talamus-search trails e5. **Corrects RS5**: "vectordb LAST cross-language" was an artifact of the weak English-centric MiniLM — against a real multilingual embedder we do NOT win raw cross-language retrieval; the edge is zero embedding infra + moats + answer quality. MIRACL ABANDONED (no Italian; multilingual-MONOlingual, not cross-language; impractical HF script download) → loader/test/datasets dep removed; book stays the cross-language test. Added bench-only: e5 steelman, llm-wiki, agent-mem scaffold, CI negatives. Report: dev/research/2026-06-rs7-competitive-expansion.md |
| RS8 (adaptive trigram) | **Closed the English ranking gap** (the RS5 residual). Detect a monolingual-ASCII corpus at index build, damp the trigram channel by MONO_TRIGRAM_SCALE=**0.3** at query. SciFact talamus-search recall 0.776→**0.797**, nDCG 0.607→**0.664**, MRR 0.562→**0.628**, hit 0.793→**0.813** — now BEATS BM25 (0.652/0.618) on all four. Two-corpora law: docs + book are NOT flagged (mixed/IT) → byte-identical, **zero regression**. CACHE_VERSION 5; env-tunable TALAMUS_MONO_TRIGRAM_SCALE; CI floor (mechanism in CI + SciFact heavy-gated nDCG≥0.63). Report: dev/research/2026-06-rs8-adaptive-trigram.md |
| RS8 (local engine + refusal) | **Zero-subscription €0 pipeline works**: fully local (gemma4:e4b as generator AND judge) talamus-search correctness **0.800** (vs 0.857 cloud), grounded + cited. Caveat measured: **5/40 generations >90 s timeout** (gemma reasoning on CPU) → a hard per-call timeout belongs in the product engine adapter. **Smart INVERTS on a slow local engine**: talamus-smart 0.700 < talamus-search 0.800 (its extra LLM call doubles timeout exposure) → plain search wins locally. **Refusal-as-weapon measured = already a strength**: talamus refusal **1.000** across cloud+local (competitors ≤0.833) via empty-context retrieval — NO coverage-gate code shipped (fragile + unneeded); expand the 6-negative set to confirm. smart multi-pass union shipped (opt-in). Report: dev/research/2026-06-rs8-local-engine-and-refusal.md |

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

1. RESOLVED: the search ≥0.92 bar is met by `search --smart` (Query2doc).
   Plain search keeps its ~0.86 lexical ceiling as the instant/free path;
   smart search is the quality path. PRODUCT.md could note both tiers
   (maintainer approval).
2. Symptom-generation variance: pin sampling (temperature 0) or opt-in 2-pass
   union (`--passes 2`, +0.028 hit, 2× ingest cost) — lower priority now that
   smart search covers the vague gap.
3. Ask re-measure on the post-consolidation brain (routing cache invalidated).
4. RS2.6 RESOLVED differently (RS8): refusal is already a Talamus strength
   (1.000 vs competitors ≤0.833, via empty-context retrieval, cloud AND local);
   a coverage-score gate was measured-out as fragile/unneeded. Real follow-up:
   expand the negatives set (6 → 30+) so the refusal win is statistically solid.
5. RS2.5: extraction granularity vs model (lite models compress specifics).
6. RESOLVED (RS8): full e2e with ollama works — talamus-search correctness 0.800
   fully local (gemma4:e4b generator + judge, €0). Caveat: 5/40 generations
   exceeded 90 s. NEW from this: lift a hard per-call timeout into the product
   engine adapter for `talamus ask` (covers both slow local models and the
   gemini-on-Windows hang).
11. **RS6 ablation faithfulness is judged vs GOLD docs, not the ask's actual
    context** → artifact (ontology_on richer context scores "less grounded in
    gold"). Fix: judge against trace `items_read`, re-run the ablation.
12. **Expand the negatives set** (currently 6) so honest-refusal is statistically
    real — today Talamus 1.000 vs competitors 0.833 is a single-question delta.
13. **Docs-corpus ASK answer-quality eval** pending (two-corpora law for any
    answer-quality claim that ships) — needs a docs brain + eval-set.
7. RS-GEN: third corpus, different domain, anti-overfitting (this would give
   the second LLM-enriched corpus the enrich findings still lack).
8. 100k-note bench; UI visual verdict from the maintainer; clean-venv install
   checklist.
9. **Chunking quality** (maintainer-flagged): `split_chunks` cuts at paragraph
   boundaries but a concept spanning a chunk boundary can still be split across
   two chunks and lose information. Investigate an overlap window between chunks
   (and/or semantic chunking) so boundary concepts survive. Measure the effect
   on ingest quality.
10. **MarkItDown (Microsoft)** (maintainer-flagged): evaluate it as an ingest
    front-end / optional extra — it already supports more file types including
    audio and video, which would extend `extract_text` beyond the current set.

## Live artifacts (not in repo)

- `C:/dev/_talamus_book` — the book brain (212 notes, enriched+consolidated,
  registered). Its eval-set `eval-cases-book.json` stays local (copyright).
- `C:/dev/_talamus_book2` — symptom-prompt A/B brain (unregistered, kept for
  comparison).
- `C:/dev/Talamus_docs_archive` — superseded specs/plans (history also in git).
