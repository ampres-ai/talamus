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
| Search latency @ 10k | ~55 ms (p95 72.6 ms re-measured 2026-07-02) | ✓ |
| Search latency @ 100k | p50 624 ms / p95 695 ms; index 208 MB (2026-07-02) | usable ✓ (bar: PRODUCT §scale) |
| Routing tokens | 12× cheaper at 10k (tree) | ✓ |

Docs corpus (129 cases, 2026-07-07: recall@5 0.522 / MRR 0.453 / hit 0.625)
floors in CI: recall ≥ 0.45, MRR ≥ 0.40, hit ≥ 0.55
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
| UI readiness foundation | Readiness service, status JSON and home next-actions now preserve onboarding state; the full product UI/redesign remains pending |
| Milestone 3A | Shared engine setup service slice: typed `ServiceResult`, canonical engine listing/default selection, engine settings load/update, Anthropic credential save without returning secrets, and CLI setup reuse |
| Milestone 3B | Shared brain registry service slice: typed list/info/register/select/rename/delete/flag results for UI/CLI parity; federation index and note promotion remain separate slices |
| Milestone 3C | Shared jobs service slice: typed list/status/log/cancel results for UI/CLI parity; resume remains in CLI runners because it depends on command-specific execution |
| Milestone 3D | Shared review queue service slice: typed list/show/apply/reject results for UI/CLI parity, including proposed-correction application without hiding failures |
| Milestone 3E | Shared query read-side service slice: typed search/read/recall results for UI/CLI parity without adding new LLM calls; ask/smart expansion remain separate |
| Milestone 3F | Shared graph service slice: typed graph-cache snapshot and ontology-neighbor results for UI/CLI parity; Obsidian-grade rendering remains a later UI milestone |
| Milestone 3G | Shared diagnostics service slice: typed doctor-style config/layout/engine/cache/index/overview checks for UI onboarding/settings and CLI reuse |
| Milestone 3H | Shared library service slice: typed read-only note list and detail metadata/markdown for UI library, inspector, and provenance surfaces |
| Milestone 3I | Shared integrations service slice: typed MCP config status/install and capture-hook snippet generation for UI settings and CLI reuse |
| Milestone 3J | Shared backup service slice: typed export/import results for UI/CLI portability, with zip path-traversal rejection before extraction |
| Milestone 3K | Shared ontology service slice: typed status/candidate review/apply/reject/deprecate/history/export for UI/CLI parity; LLM induction/eval remain separate |
| Milestone 3L | Shared ingestion service slice: typed ingest preview/confirmation/run for UI/CLI parity, preserving the no-LLM-call consent gate for large local files |
| Milestone 3M | Shared scan service slice: typed repository scan preview/confirmation/secret-block/queue/run for UI/CLI parity, preserving zero LLM construction before approval |
| Milestone 3N | Shared enrich service slice: typed symptom-vocabulary preview/confirmation/run for UI/CLI parity, preserving the estimate-before-batches consent gate |
| Milestone 3O | Shared consolidation service slice: typed duplicate-group proposals and reviewed-group apply operations for UI/CLI parity without forcing a second LLM call after review |
| Milestone 3P | Shared verification service slice: typed batch provenance/content reports, single-note verification, and explicit correction application for UI/CLI parity |
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
| P2 tiering (2026-07-02) | **Per-task model+effort tiering shipped** (`talamus.routing`): ten TaskClasses, cost-minimizing defaults (7 economy / 3 quality), EngineRouter memoized per (tier,effort), StaticRouter shim, config `task_tiers`+`provider_models`; EVERY LLM call site converted (CLI/services/MCP/webapi/UI/benchmarks). Flags smoke-tested live: claude `--model`, codex `-m`+`model_reasoning_effort` (gpt-5.4-mini/gpt-5.5, xhigh accepted), gemini `-m`. Engine failures now surface the real CLI error (stdout, e.g. 401). Evidence: dev/research/2026-07-p2-tiering-savings.md. Remaining P2 slices: limits+timeout, kimi/opencode |
| Perfection push (2026-07-02) | Maintainer-directed quality sprint, all merged: **global ontology** (ONE schema across all brains under TALAMUS_HOME, per-brain opt-out, auto-migration — spec dev/specs/2026-07-02-global-ontology-design.md); **MCP moats** (ask with citations, verify-against-source, read_note as-of); **engines opencode + antigravity-cli** (live-verified: stdin prompt, read-only pinning, --variant effort); **usage-limit detection + configurable timeout** (EngineLimitReached, TALAMUS_ENGINE_TIMEOUT); **UI**: `talamus ui` now opens the React workbench, Flet fully retired (codex-drafted), inspector gains the TIME (as-of view) and VERIFIABILITY (one-click verify) moat panels (browser-verified); **chunk overlap** (CHUNK_OVERLAP=1000, deterministic, count-stable — closes open front #9; codex-drafted); `talamus import-vault` (P9 md/Obsidian 1:1, no LLM); negatives 8→30; 100k bench (p50 624 ms) |
| P7 Flet retirement (2026-07-02) | Legacy Flet app/views/theme/graph and their tests removed at React workbench parity. `talamus ui` remains the local web workbench; `ui/physics.py` stays for server-side graph layout. The `ui` extra now depends on FastAPI/Uvicorn/pywebview, not Flet. |
| M2 consent-first hook (2026-07-07) | Capture hook is consent-first (D6): setup shows the privacy contract (transcript + git diff → worth-remembering gate → THIS brain; audit at `.talamus/logs/capture.log`), asks once (`--capture ask\|yes\|no`; non-interactive ⇒ no), installs into `.claude/settings.json` only on yes (`install_capture_hook`, merge + idempotent); `talamus hook --install` for later consent; hook command quotes roots with spaces |
| smart multi-pass exposed (2026-07-07) | `talamus search --smart --passes N` now reaches `expand_query_multi` (RS8's variance-smoothing union was previously shipped but CLI-unreachable); `--passes` without `--smart` is a clear error; `passes=1` stays the cached single-pass path, byte-identical behavior |
| M1 magic-demo harness (2026-07-07) | The D7.1 recall loop is scripted and self-verifying: `scripts/demo/run_magic.py` (consented setup → real `hook-run` on a realistic transcript → note with session provenance → fresh-session recall must cite it) in `--fake` (CI, deterministic in-process engine, real index/registry paths) and real (subprocess CLI + cited `ask`) modes; `tests/test_talamus_demo_magic.py` covers the arc and the honest below-gate skip. Remaining for D7.1: the recorded real-engine 60s take |
| C1 code-health (2026-07-07) | Evidence-backed dead-code sweep executed: removed `progress.py`, `RELATION_TYPES`, `REVIEW_STATUSES`, `preview_enrich` (preview = `run_enrich(confirmed=False)`), `detect_engines`, `provenance_report`; the 7 duplicated lenient model-JSON parsers centralized into `talamus/model_json.py` (`json_array`/`json_object`/`balanced_objects`, hostile battery green); readiness reuses `canonical_provider` + `integrations.mcp_installed`; `__version__` 0.1.0→1.0.0 (was lying vs pyproject); `talamus-mcp` argparse description says read/write. Kept: `expand_query_multi` (exposed via `--passes`); webapi seam items deferred to the security workstream |
| Launch truth (2026-07-07) | Maintainer-ordered truth pass: the 6 Flet-era eval cases dropped from `examples/eval-cases-real.json` (135→129; re-measured on the frozen docs corpus: recall@5 0.512→0.522, MRR 0.458→0.453, hit 0.627→0.625 — floors untouched; the corpus FIXTURE stays frozen, it is the benchmark haystack); PRODUCT.md refreshed to reality (7-engine list ×2, the real 9-view React workbench + inspector moats, unsourced "~3 min" and "~98% vector-DB" claims replaced with measured RS5/RS7 anchors). Branch cleanup: 32 fully-merged branches deleted, `feat/ask-eval` deleted as superseded (its stratified-subset fix lives in main's `ask_eval/run.py`), 3 stale worktrees removed; remaining: `main`, the active security-session branch, this session |
| D7.2 MCP cross-agent (2026-07-07) | `talamus mcp install [--agent auto\|claude\|cursor\|codex\|all]` connects every agent in one command: `.mcp.json` (Claude Code), `.cursor/mcp.json` (Cursor, auto when the project has `.cursor/`), and a GLOBAL `codex mcp add talamus → talamus-mcp` registration (no `--root`: the brain resolves from the project codex runs in; remove-then-add = idempotent; resolved shim path — bare `codex` is WinError 2 on Windows). Verified live: one `--agent all` run configured all three, `codex mcp list` shows talamus enabled. Hermeticity: `CODEX_HOME` redirected in `tests/__init__.py` + `dev.py` so tests can never touch the real `~/.codex/config.toml`. Cursor path follows its documented format (app not on this machine) |
| A1 engine verify (2026-07-07) | Setup probes the chosen engine with one tiny live call before declaring success (`--verify-engine`/`--no-verify-engine`; AUTO = only a real terminal — stdin+stdout ttys, no injected router — so scripts/CI/tests/harnesses never fire an unasked LLM call); on failure a loud stderr warning with the per-engine fix (opencode: `opencode auth login` + provider/model; all seven engines have hints); setup still completes (brain/MCP/hook valid). Verified live: `setup --engine opencode --verify-engine` → "engine verified: 'opencode' answered (ok)" |
| B1 one-screen benchmark (2026-07-07) | `python benchmarks/run.py --tier one-screen` renders the 11-row honest table (frugality −97.7%, verifiability 100%, €0, book cross-language win, THE HONEST LOSS to multilingual-e5, SciFact post-RS8, judged answers, ontology ON/OFF, fully-local, refusal, latency) + one honest paragraph; pure assembler over committed artifacts (measures nothing, fails loudly on a missing one); canonical render `benchmarks/results/one-screen.md`, user page `docs/benchmarks.md`; FAST test asserts every source cell resolves to a real file. Codex draft hung mid-job (killed after 3.5h silent) — assembler written by hand, its test kept after de-hardcoding C:/tmp and fixing subprocess stdout decoding to utf-8 |
| M1 real-engine proof (2026-07-07) | The magic arc ran END-TO-END with a real engine on this machine (`run_magic.py --dir ... --keep`, claude-cli): session about the FTS5 decision captured by the real hook → 4 cross-linked Italian notes with wikilinks + session provenance → fresh-session `recall` cited them → full `ask` answered with citations [1–4] and the honest trade-off. 103 s total; exit 0 (self-verified). Remaining for D7.1: the recorded take (engine/model choice can shave time — extraction dominates) |
| UI-parity API (2026-07-08) | The React workbench reaches CLI parity on integrations + engines, backend only (services + thin FastAPI adapters, every POST behind the S1 token+Origin guard): GET `/api/integrations` (report extended with cursor_installed / codex_on_path / hook_installed), POST `/api/integrations/mcp` `{agent: auto\|claude\|cursor\|codex\|all}` → per-agent results (missing codex = skip under auto/all, error when explicit — the CLI contract), POST `/api/integrations/hook` (consent copy stays in the UI, D6 — the endpoint just installs), POST `/api/engines/probe` → ONE tiny live completion via `build_provider` returning verified/error + `limit_reached` (the honest on-demand quota check) + the per-engine hint; `_ENGINE_HINTS` refactored out of `cli/lifecycle.py` into `services/engines.py` (ONE hints source for CLI and UI, CLI behavior identical). Codex draft hung at start — implemented by hand; its leftover webapi test kept and extended (de-hardcoded `C:/tmp`, added limit/skip/unknown-agent cases) |
| F2-B ontology inference (2026-07-08) | **Closure, not scoring** (spec dev/specs/2026-07-08-ontology-inference-design.md, shipping order 1): relation-type properties (`inverse_of`/`transitive`/`symmetric`) INDUCED purely structurally — a property is proposed only with corpus witnesses (transitive chains count only when an explicit A→C edge exists; ≥8 support pairs, ≥3 distinct notes) — through the EXISTING candidate → review → promote lifecycle (`talamus ontology infer`, candidate kind `property`, versioned `property_candidate_induced`/`property_promoted`/`property_rejected` schema events). Promoted properties drive a deterministic, cycle-safe closure (transitive depth cap 2) into the derived cache `.talamus/cache/ontology_inferred.json`, rebuilt on reindex and schema change; every inferred edge carries `{inferred: true, rule, via, schema_version}`. `neighbors` (CLI `--no-inferred`, MCP `include_inferred`, graph service param) shows inferred edges marked with rule + derivation. ZERO LLM calls; ask/rank/indexes untouched — the flag-gated ask-context ablation is the separate next step (spec order 3). 12-test module tests/test_talamus_ontology_inference.py; gate ALL GREEN (645 tests) |

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

> **The forward plan now lives in [dev/ROADMAP.md](ROADMAP.md)** (rewritten
> 2026-07-02 as the launch-first legacy document). The launch-critical order is:
> **Phase S — security hardening (BLOCKING)** — a 2026-07-02 audit found a critical
> (workbench CSRF / DNS-rebinding) + symlink exfiltration + MCP path traversal;
> full findings in `scratchpad/audit_security.txt` and summarized in the roadmap —
> then Phase M (developer magic), A (onboarding), U (UX), P (performance), B
> (benchmark), C (code-health + docs truth), L (launch). The items below are the
> older research queue, folded into the roadmap's post-launch backlog where still open.

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
12. RESOLVED (2026-07-02): negatives set expanded 8 -> 30 (IT/EN, incl.
    adversarial near-misses) in benchmarks/ask_eval/negatives_ci.json; re-run the
    heavy refusal eval on it when convenient to refresh the numbers.
13. **Docs-corpus ASK answer-quality eval** pending (two-corpora law for any
    answer-quality claim that ships) — needs a docs brain + eval-set.
7. RS-GEN: third corpus, different domain, anti-overfitting (this would give
   the second LLM-enriched corpus the enrich findings still lack).
8. PARTIALLY RESOLVED (2026-07-02): 100k bench done (search p50 624 ms, usable —
   dashboard row) and the clean-venv cold install verified (pip non-editable ->
   demo -> search, exit 0). Remaining: the UI visual verdict from the maintainer.
9. RESOLVED (2026-07-02): deterministic chunk overlap shipped (CHUNK_OVERLAP=1000,
   count-stable, overlap=0 = historical output). Remaining follow-up: measure the
   effect on ingest quality with the ingest-quality benchmark (P3).
10. **MarkItDown (Microsoft)** (maintainer-flagged): evaluate it as an ingest
    front-end / optional extra — it already supports more file types including
    audio and video, which would extend `extract_text` beyond the current set.

## Live artifacts (not in repo)

- `C:/dev/_talamus_book` — the book brain (212 notes, enriched+consolidated,
  registered). Its eval-set `eval-cases-book.json` stays local (copyright).
- `C:/dev/_talamus_book2` — symptom-prompt A/B brain (unregistered, kept for
  comparison).
- `C:/dev/Talamus_docs_archive` — superseded specs/plans (history also in git).
