# Changelog

All notable changes to Talamus are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning once it reaches a public release.

## [Unreleased]

Pre-release. The project was renamed **Kortex → Talamus**.

### Engine tiering & v1 hardening (P2/P9/P11, 2026-07-01/02)

- **Per-task model+effort tiering** (`talamus.routing`): every LLM call resolves
  through an `EngineRouter` by task class (extraction, routing, expansion, answer,
  verify, enrich, consolidate, naming, session capture) — bulk work runs on the
  cheap tier (claude haiku / codex gpt-5.4-mini / gemini flash), the answer you
  read and source verification on the strong tier. Config: `task_tiers` +
  `provider_models` overrides. Top quality, minimal subscription burn.
- **Usage-limit detection + hard timeout**: an exhausted engine limit now raises
  a clear, actionable error (wait or switch engine) and resumable jobs pause
  instead of crashing; the per-call timeout is configurable via
  `TALAMUS_ENGINE_TIMEOUT`. Engine failures surface the real CLI error (e.g. a
  401) instead of a blind exit code.
- **`talamus import-vault <dir>`**: import a Markdown/Obsidian vault (or a Notion
  markdown export) 1:1 with **zero LLM cost** — titles, tags, aliases and
  `[[wikilinks]]` preserved, links become graph edges, idempotent re-runs.
- **Measured at scale**: search p95 72.6 ms @ 10k notes, p50 624 ms @ 100k notes
  (sqlite-fts5, 208 MB index); cold `pip install` verified in a clean venv;
  honest-refusal negatives set expanded 8 → 30.

### Final-product phase (PRD M0–M11, 2026-06-10/11)

- **Measured baseline**: real 120-case eval-set (`examples/eval-cases-real.json`),
  deterministic corpora, latency/cost curves (`docs/benchmarks/`).
- **Multi-brain**: machine-wide registry, `talamus brains` group (use/info/rename/
  delete/register/set/index/promote), federated read index with pointers + markers,
  `--scope` / `--all-brains` on read commands, `where --json`; **`talamus init` now
  always targets the current directory** (bug fix).
- **Jobs & review**: persistent resumable jobs (`talamus jobs`), review queue
  (`talamus review`) — crashes resume, cancels never corrupt notes, rejections stay
  logged.
- **Repo scan**: `talamus scan` — plan first/spend later (dry-run with estimates),
  profiles docs/code/all, `.gitignore` respect, **secret redaction with
  stop-and-confirm**, code-aware digests (ast), resumable job.
- **Persistent indexes**: sqlite/FTS5 (+ JSON posting fallback) — search p95 at
  10k notes **8458ms → 34ms (~249x)**; structured domain routing by stable ids;
  `ask --trace`; `eval --scale`.
- **Ontology Lab** (the differentiator): evidence layer → deterministic candidate
  induction → versioned schema candidate/active/deprecated with promotion rules →
  runtime re-typing + typed-first expansion with **measured retrieval lift**
  (`talamus ontology ...`); research review in `docs/research/`.
- **Full temporal model**: valid-time claim overlay, robust `--as-of` parsing
  (year/month/date/tz), corrections close+open claims, `talamus timeline`,
  `ask`/`read --as-of`. Cache v2 (migration: `talamus reindex`).
- **Active verifiability**: `verify --all/--stale/--source`, provenance health,
  corrections proposed to review (never silent overwrites).
- **Final CLI**: state dashboard on bare `talamus`, JSON coverage, help under
  100 columns, snapshot tests, `--plain/--no-color`.
- **UI workbench**: 11 views (Home/Chat/Cerca/Note/Domini/Grafo/Timeline/Ingest/
  Review/Ontologia/Impostazioni) over the SDK, `talamus ui --web --port`,
  headless smoke tests. *(runtime rendering: verify with `talamus ui`)*
- **MCP finalized**: read tools + history/sources/ontology_status; write tools
  with explicit scopes; `propose_note` routes uncertain knowledge to review;
  capture decisions logged.

### Added

- **CLI**: no-arg status panel, `quickstart`, smart `init` (engine auto-detect,
  `--engine`), enhanced `doctor` (engine/cache/notes), `--json` on read commands,
  global+project brain **scoping** (`--root` / `--brain` / `--global`, `TALAMUS_HOME`),
  `brains`, `where`, `export`/`import`, shell `completion`, and `demo`
  (an instant, LLM-free example brain).
- **Engines**: pluggable LLM adapters via a `build_provider` factory — `claude-cli`,
  local **Ollama**, and the **Anthropic API**; selected from config (`llm_provider`,
  `llm_model`). The CLI and MCP server build the engine from config.
- **Onboarding**: `talamus mcp install` (writes `.mcp.json`) and `talamus hook` /
  `hook-run` (a robust Claude Code capture hook). 10-minute quickstart.
- **Quality**: `ruff` + `mypy` + a `dev.py` runner, multi-OS CI, an exception
  hierarchy with actionable messages, logging, config validation, **normalized
  source files written to disk**, cache schema versioning, and a benchmark harness.
- **Docs**: a 10k-star README, internal architecture doc, a security policy, and
  this docs site.
- **Retrieval & meaning**: a hierarchical **domain overview** (`talamus overview`,
  hybrid graph-clusters + LLM naming) with overview-routed `ask`; deterministic
  **reranking** (`rank.py`: graph + BM25 union with an exact-name boost — no more
  funnel); a **context token budget** (`budget.py`) for flat answer cost; an
  **evaluation harness** (`talamus eval`, recall@k / precision@k / MRR); a light
  Italian stemmer and last-resort query expansion; **concept consolidation**
  (`talamus consolidate`).
- **Time & verifiability**: a **bitemporal MVP** — `talamus history [--as-of]`,
  invalidate-not-delete versioning; **source-correction** (`talamus verify [--apply]`)
  against the preserved original; typed-relation listing/pruning (`talamus relations`).
- **Ingestion**: multi-format `talamus ingest` for files, folders (recursive,
  incremental), and URLs — Markdown/text, **PDF** (`pdf` extra), **DOCX** and **HTML**
  (stdlib), with content-hash skip of unchanged sources.
- **Interfaces**: a native **Flet desktop/web UI** (`talamus ui`, `ui` extra) — chat,
  search, note view with clickable wikilinks, and domain browsing, calling the SDK
  directly (no API); the MCP server gains an **`overview`** tool (cached domain map,
  no LLM cost).
- **Polish**: `talamus --version`; `--limit` on `search`/`recall`; **PEP 561**
  `py.typed` so SDK consumers get type hints; folder ingest now **reports failed files**
  instead of dropping them silently; clear messages when the engine returns empty output;
  the UI surfaces engine errors instead of hanging, and renders wikilinks with spaces.

### Changed

- Package `kortex` → `talamus`; CLI `kortex` → `talamus`; config `kortex.json` →
  `talamus.json`; cache `.kortex/` → `.talamus/`; env `KORTEX_*` → `TALAMUS_*`.
