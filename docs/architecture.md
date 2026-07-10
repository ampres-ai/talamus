# Architecture

How every part of Talamus works: what each module does, how data flows, and
where to look. File references are relative to `src/talamus/`. The core is
**Python stdlib-only**; optional features (UI, MCP, PDF, benchmarks) live
behind extras and adapters.

## Anatomy of a brain on disk

```text
<brain root>/
  talamus.json            ← config: llm_provider, llm_model, language, providers
  notes/*.md              ← HUMAN TRUTH: Obsidian-compatible notes, frontmatter
                            (id, title, aliases, tags, confidence, sources)
  .talamus/
    raw/                  ← preserved source copies (files, URL dumps, chunks)
    normalized/           ← sectioned normalized view (provenance anchors)
    cache/
      notes/*.json        ← MACHINE TRUTH: full CanonicalNote (relations,
                            retrieval_text, proposed_links, sources, history ptr)
      index.sqlite        ← persistent search index (FTS5) — derived
      postings.json       ← fallback search index — derived
      graph.json          ← note/source graph — derived
      ontology.json       ← typed edges + concepts — derived
      overview.json       ← domains (id, name, description, members) — derived
      overview-tree.json  ← macro-areas over domains — derived
      schema.json         ← ontology schema (versioned, candidate/active)
      claims.jsonl        ← valid-time facts, append-only
      history/            ← note versions, append-only
      jobs/               ← resumable job records + logs
      ingested.json       ← content hashes for incremental ingest
    logs/capture.log      ← agent-capture audit trail
```

Hybrid truth model: Markdown is the human-editable truth for prose fields;
cache JSON is the machine truth for provenance, relations and retrieval.
`talamus reindex` re-reads the Markdown, merges human edits into the machine
records, and rebuilds every derived index. A bump of `CACHE_VERSION` (in
`store.py`) forces a reindex migration.

## Data model (`models.py`)

`CanonicalNote`: note_id, title, aliases, folder, tags, summary,
retrieval_text, body_sections (fixed structural keys used as identifiers, not
display text), proposed_links (anchor→target), relations (source, relation,
target, confidence), sources (`SourceRef`: raw_path, normalized_path#section,
locator, source_hash over extracted TEXT, supported_claims), confidence,
timestamps.

## Ingest pipeline (`ingest.py`, `sources.py`, `normalize.py`, `extract.py`)

1. `extract_text` dispatches on suffix: pdf (pypdf, optional extra), docx
   (stdlib zip+xml), html (stdlib strip), md/txt. URLs via `read_url`.
2. Incremental: a content hash in `ingested.json` skips unchanged files.
3. **Chunking** (`split_chunks`): deterministic paragraph split with a fixed
   overlap so boundary concepts survive. More than one chunk → `ingest_large`:
   a resumable job, one extraction call per chunk, progress persisted after
   each, engine failures pause (resumable), single bad chunks retried once and
   then recorded without aborting the run. Chunk files are always `.md`
   (extracted text). One reindex at job end (crash-safe). CLI consent gate:
   the estimate is printed and the job runs only with `--yes`.
4. `normalize_text` → sections with stable ids (provenance anchors);
   `source_hash` is the sha256 of the extracted text (not file bytes —
   platform newlines and binary formats would break comparison).
5. `extract_notes` (`extract.py`): one English prompt with an output-language
   directive. The model returns a JSON array of notes; the parser is
   deliberately forgiving of malformed model output (see `model_json.py`).
   Every note carries an English canonical alias, bilingual retrieval text and
   English relation verbs (see [design principle 9](design-principles.md)).
6. `_compile_package`: phase 1 writes all note JSONs (merging on the same id —
   `merge_notes` unions aliases/tags/relations/sources/retrieval_text and
   keeps the higher-confidence prose); phase 2 renders Markdown with a
   whole-batch registry so same-batch wikilinks resolve (self-links dropped);
   then `rebuild_indexes`.

Also: `ingest_dir` (recursive, failures recorded), `ingest_url`, `ingest_text`
(agent insights, scan digests), and `remember_session` (transcript + diff
behind a worth-remembering gate, audited in `capture.log`).

## Retrieval (`indexes.py`, `textutil.py`)

Three blended channels, **no embeddings**:

```text
score = lexical_bm25 + 0.7 · trigram(title+aliases) + 0.3 · trigram(summary)
```

- Lexical: a bilingual light stemmer (`textutil.tokens`), a field-weighted
  haystack (title ×3, aliases ×2, tags, retrieval_text, summary), BM25.
- Trigram channels: character 3-grams — the **cognate bridge**
  (architettur*ali* / architectur*e*) that buys cross-language recall without
  embeddings. On a corpus detected as monolingual-ASCII at index build, the
  trigram channel is damped (tunable via `TALAMUS_MONO_TRIGRAM_SCALE`) — this
  measured fix closes the English-only ranking gap against BM25.
- Long "hub" notes are damped by a length penalty so they cannot accumulate
  blended score across every query.
- Backends: sqlite FTS5 (4 columns, per-column bm25 weights) preferred; a
  deterministic JSON postings fallback; a legacy in-memory path. Channels are
  normalized per query, then weighted-summed.

Cross-language search works **by construction**: English canonical aliases
and bilingual retrieval text are written at ingest, symptom phrasings via
`talamus enrich`.

## Ask path (`ask.py`) — the user-facing pipeline

```text
question
  → routing (LLM): macro-areas (if the tree exists) → domains, by stable id,
    validated against the map
  → LLM query EXPANSION (your LLM acts as the embedding model: it translates
    your phrasing into corpus vocabulary; +1 call, cached)
  → selection (deterministic): the chosen domains' members ranked against
    question+expansion via the persistent index, plus 2 top global hits
    outside the chosen domains (the escape hatch for routing mistakes)
  → budget (fit_to_budget, TALAMUS_CONTEXT_BUDGET)
  → answer (LLM): only from context, cites [n], answers in the question's
    language, refuses honestly when context is insufficient; sources legend
```

With no overview: persistent-index seeds + 1-hop typed-first ontology
expansion (active only when seeds are scarce); still nothing → an LLM
query-expansion retry. `--as-of` reads historical versions; `--trace` returns
the full route (areas, domains, expansion, items read, tokens). Federated
extras (`[central]` items) are appended by the CLI layer per scope policy.

## Ontology (`ontology.py`, `ontology_lab.py`, `relations.py`)

- `build_ontology`: edges from note relations (normalized surfaces) +
  proposed links (type "related"); rebuilt at every reindex with the active
  surface map, so **promotions re-type edges globally**.
- The Ontology Lab: an evidence layer → deterministic clustering of
  unexplained surfaces → one LLM naming call (English definitions) → a
  versioned schema (candidate/active/deprecated, full history) → promotion
  only by rule: support ≥ 8 across ≥ 3 distinct notes (`--force` overrides,
  logged). The schema is global across your brains (per-brain opt-out).
- `talamus ontology infer` induces relation-type *properties*
  (inverse/transitive/symmetric) purely structurally from corpus witnesses,
  through the same candidate → review → promote lifecycle; promoted
  properties drive a deterministic, cycle-safe closure into a derived cache
  of inferred edges, each carrying its rule and derivation. Zero LLM calls.
- Runtime effect: typed edges come first in context expansion and in the UI
  graph; domain clustering runs on the ontology edges. Its measured value is
  in **structure** (clustering, routing, navigation) and in answer quality —
  ontology-in-ranking boosts were tried and rejected with data.

## Domains & hierarchical overview (`domains.py`)

- Structural clusters come from union-find over the ontology edges.
- Small brains get a single full-partition naming call. Bigger brains use
  **batched induction** (a single prompt collapses at scale): giant clusters
  get a dedicated split call; mid clusters are named in one call echoing only
  a numeric index (first title as the deterministic fallback); strays are
  assigned in batches against the named domains. A malformed answer hurts
  only its slice.
- Domains get stable ids (`dom-*`); enough domains → an overview tree groups
  them into macro-areas (`area-*`), so routing cost grows like log(N).

## Temporal (`temporal.py`, `timeline.py`)

- Transaction time: note versions in append-only history; `note_as_of`.
- Valid time: `claims.jsonl`, append-only; `record_claim` /
  `invalidate_claim` (corrections close the old claim and open the new one —
  never delete); `claims_as_of`, `note_timeline`. `parse_when`: partial dates
  mean the END of the period; naive datetimes warn and use the local tz.

## Verification (`correct.py`)

- `provenance_status` (no LLM): resolves the RAW source first (the hash was
  computed on extracted text, so comparisons re-extract — never file bytes);
  the normalized view proves existence only; flags source_missing /
  source_changed / low_confidence.
- `verify_batch`: stale notes → review items without an LLM; checked notes →
  the LLM compares them against their source; mismatches become PROPOSED
  corrections in the review queue. `review apply` writes them with history
  preserved.

## Curation

- **`enrich.py`**: symptom-vocabulary enrichment — batched, English prompt
  echoing note ids, idempotent (marker in retrieval_text), guard-rails for
  weak models, estimate + `--yes`, one reindex at the end.
- **`consolidate.py`**: duplicate detection (one call, with balanced-object
  salvage for truncated answers) → groups PROPOSED; `apply_consolidation`
  accepts only REVIEWED groups (models tend to lump related-but-distinct
  concepts); the merge unions retrieval text and accumulates provenance.

## Jobs (`jobs.py`)

Persistent records under `cache/jobs`, created BEFORE the first expensive
call. States: queued→running→completed/failed/cancelled (+paused).
`run_items`: the done-set is persisted per item, cancel is cooperative
between items, failures leave a resumable record, and stale `running` records
(hard kill) are adopted on resume.

## Multi-brain (`registry.py`, `scope.py`, `federation.py`)

The registry lives at `TALAMUS_HOME/registry.json`. Scope policies:
project-only / central-only / project+central (default) / all. Federation is
a pointer index (derived); central reads federate into search/ask
(`[central]` markers), writes stay local unless `--all-brains`;
`brains promote` moves a note to central. See [Multi-brain](multi-brain.md).

## Engines (`adapters/llm.py`, `routing.py`)

`LLMProvider` protocol = `complete(prompt) -> str`. Adapters: claude-cli,
codex-cli (pinned to a read-only sandbox), antigravity-cli, opencode
(read-only plan agent), ollama (CLI or HTTP), anthropic-api (key from env or
the machine credential store; env wins), and the deprecated gemini-cli
(kept for old installs; Talamus warns and points at antigravity-cli).
Model passthrough via config `llm_model`. Executables are resolved with
`shutil.which` (Windows shims included). All model JSON is parsed defensively
(lenient parsing, balanced-object salvage, batch isolation) — enforced by the
hostile-model CI battery.

Every LLM call resolves through per-task **model + effort tiering**
(`routing.py`): ten task classes with cost-minimizing defaults (bulk work on
the cheap tier, the answer you read on the strong tier), overridable via
`task_tiers` + `provider_models` in `talamus.json`. Usage-limit exhaustion
raises a clear, actionable error, and `TALAMUS_ENGINE_TIMEOUT` caps a single
call.

## Interfaces

All front ends route through `services/` wherever a shared contract exists:
typed `ServiceResult` contracts are the seam between the core and the
interfaces, so behaviour stays identical across CLI, MCP, UI and SDK.

- **Shared services** (`services/`): readiness, engine setup, ingestion
  preview/consent/run, repository scan, enrichment, consolidation,
  verification, brains registry, jobs, review queue, read-side query, graph
  snapshots, diagnostics, library, integrations (MCP install + capture hook),
  backup export/import, and ontology operations.
- **CLI** (`cli/` package): the full surface; bare `talamus` is the
  dashboard; `--json` on read commands; `--root`/scope flags; consent gates.
- **MCP** (`mcp_server.py`, optional extra): read tools (search, read_note,
  recall, ask, verify, neighbors, overview, history, sources,
  ontology_status) + write tools (remember, ingest_text with scope,
  propose_note → review, review_list/apply/reject). Local stdio; optional
  localhost HTTP. See [For agents](agent-tool-calling.md).
- **SDK** (`recall.py`): read-side functions for embedding in agent code.
- **Web workbench** (`webapi/` + the `webui/` React app, optional `ui`
  extra): FastAPI + a prebuilt React SPA launched by `talamus ui` in a
  pywebview window by default, or a browser with `--web`. Every mutating
  endpoint requires the per-launch UI token (see [SECURITY.md](https://github.com/GCrapuzzi/Talamus-Wiki/blob/main/SECURITY.md)).
  `ui/physics.py` is the pure server-side force layout used by
  `webapi/graph_layout.py`.
- **Hook** (`scripts/talamus-session-hook.py`): session capture on agent
  session end, consent-first.

## Measurement instrumentation (`eval.py`, `corpus.py`, `bench.py`)

- `eval.py`: recall@k / precision / MRR / hit-rate / negative rejection over
  a pluggable retriever; cases from JSON; category breakdown. CLI
  `talamus eval` — see [Measuring retrieval](evaluation.md).
- `benchmarks/retrieval_lab.py` (outside the package): in-memory ablation
  variants (tokenizers, channels, weights, bundle selection, rejection
  analysis) — retrieval hypotheses run here first; only multi-corpus winners
  ship.
- `corpus.py`: deterministic corpora built from frozen fixtures, so the
  regression floors in CI compare like with like.

## The quality gate

`python dev.py` = ruff check + ruff format check + mypy + full unittest,
cross-platform. CI runs it on Linux/macOS/Windows across Python 3.11–3.13.
