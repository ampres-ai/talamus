# Changelog

All notable changes to Talamus are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning once it reaches a public release.

## [Unreleased]

### Added

- A dedicated OpenAI skills-only plugin bundle and deterministic reviewer
  dossier for guarded, CLI-first local project memory.
- A Cursor Marketplace plugin manifest that bundles a dedicated, consent-aware,
  CLI-first memory skill.
- A repository-level goose Open Plugin that installs the consent-aware Talamus
  memory skill and starts the pinned local MCP server for the active project.

### Fixed

- The Cursor plugin no longer starts Talamus with the plugin cache as an
  ambiguous `--root .`. Optional MCP setup now requires an explicitly approved
  persistent tool install and verifies the workspace's absolute root.

### Security

- Agent skills and answer generation now treat files, URLs, transcripts, MCP
  responses, and retrieved notes as untrusted data; embedded requests cannot
  override consent, reveal secrets, or trigger commands and tools.

## [1.0.3] - 2026-07-20

### Added

- Consent-safe `llms-install.md` instructions for AI coding clients and MCP
  marketplaces, including standard stdio configuration and verification steps.
- Community issue forms, pull-request template, code of conduct, private
  vulnerability-reporting link, and reusable social/marketplace artwork.

### Changed

- Vite is updated to 6.4.3 and esbuild to 0.25.12; the packaged React workbench
  assets are rebuilt from the patched toolchain.
- CI and release workflows use Node 24-compatible `actions/checkout@v6` and
  `actions/setup-python@v6` runtimes.
- README badges, roadmap status, release guidance, and tracked fixture links now
  reflect the public `ampres-ai/talamus` project and official MCP Registry entry.

### Security

- Four Dependabot findings in the Web UI development toolchain are resolved,
  including the high-severity Vite development-server advisory and three
  moderate Vite/esbuild advisories. The bundled production UI contains no Node
  development server.

## [1.0.2] - 2026-07-20

### Added

- **Official MCP Registry metadata**: `server.json` describes the PyPI package,
  stdio transport, source repository, and deterministic launch arguments.
- **Registry-native MCP launch**: `talamus mcp serve` starts the existing stdio
  server from the main CLI, while `talamus mcp install` keeps its current behavior.
- **Launch demo**: the README now shows a reproducible animated session-capture
  and cited-recall walkthrough near the top of the page.

### Changed

- Release automation publishes MCP metadata through GitHub OIDC after PyPI
  succeeds; no long-lived registry token is stored.
- PyPI homepage and documentation metadata now point to the public Talamus docs.

## [1.0.1] - 2026-07-20

### Added

- **Freshness by default**: the bitemporal `supersedes` handover preserves old
  notes and claims while default answers use the current successor. Dated,
  claims-aware context and ingest-time replacement detection complete the flow.
  The committed temporal benchmark records current-answer rate `1.000` and stale
  rate `0.000` in `benchmarks/results/2026-07-14-temporal.json`.
- **Curator and watch mode**: deterministic health checks across registered brains,
  a deep provenance pass, safe cache repairs, and consent-bounded auto-ingest.
- **Workbench round**: instant plain search, AI-expanded search, capture retry,
  plain-language brain flags, and opencode MCP installation.
- **Engine resilience**: provider fallback on exhausted quotas or missing CLIs,
  plus durable capture parking for engine limits and hostile model output.
- **LongMemEval adapter hardening**: incremental artifacts, question offsets,
  deferred local judging, economy-tier extraction, and question-level workers.

### Changed

- Canonical project ownership, package metadata, badges, links, and user-agent now
  point to `ampres-ai/talamus` and identify Talamus as an Ampres project.
- The release workflow now enforces tag/version parity and runs the complete
  quality gate before building or publishing distributions.

### Fixed

- `scope=all` always includes the current brain, even before the federated index
  exists, so a clean-install `talamus demo` is immediately searchable.
- Note-version timestamps remain strictly ordered on coarse-resolution clocks,
  so immediate consecutive writes are distinguishable with `--as-of`.

### Security

- The complete Git history is scanned with Gitleaks; the only allowlisted
  fingerprints are three synthetic credentials in the secret-detection tests.

## [1.0.0] - 2026-07-03

Initial public PyPI release. The project was renamed **Kortex → Talamus**.

### Engine tiering & v1 hardening (2026-07-01/02)

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

### Final-product phase (2026-06-10/11)

- **Measured baseline**: real 120-case eval-set (`examples/eval-cases-real.json`),
  deterministic corpora, latency/cost curves.
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
  (`talamus ontology ...`).
- **Full temporal model**: valid-time claim overlay, robust `--as-of` parsing
  (year/month/date/tz), corrections close+open claims, `talamus timeline`,
  `ask`/`read --as-of`. Cache v5 (migration: `talamus reindex`).
- **Active verifiability**: `verify --all/--stale/--source`, provenance health,
  corrections proposed to review (never silent overwrites).
- **Final CLI**: state dashboard on bare `talamus`, JSON coverage, help under
  100 columns, snapshot tests, `--plain/--no-color`.
- **UI workbench**: 9 React views (Home/Ask/Graph/Library/Import/Ontology/
  Review/Brains/System), launched by `talamus ui` in a pywebview window or by
  `talamus ui --web --port` in a browser. *(runtime rendering: verify with
  `talamus ui`)*
- **MCP finalized**: read tools + history/sources/ontology_status; write tools
  with explicit scopes; `propose_note` routes uncertain knowledge to review;
  capture decisions logged.

### Added

- **CLI**: no-arg status panel, `quickstart`, smart `init` (engine auto-detect,
  `--engine`), enhanced `doctor` (engine/cache/notes), `--json` on read commands,
  global+project brain **scoping** (`--root` / `--brain` / `--global`, `TALAMUS_HOME`),
  `brains`, `where`, `export`/`import`, shell `completion`, and `demo`
  (an instant, LLM-free example brain).
- **Engines**: pluggable LLM adapters via a `build_provider` factory —
  `claude-cli`, `codex-cli`, `gemini-cli`, `opencode`, `antigravity-cli`,
  local **Ollama**, and the **Anthropic API**; selected from config
  (`llm_provider`, `llm_model`). The CLI and MCP server build the engine from
  config.
- **Onboarding**: `talamus mcp install` (writes `.mcp.json`) and `talamus hook` /
  `hook-run` (a robust Claude Code capture hook). 10-minute quickstart.
- **Quality**: `ruff` + `mypy` + a `dev.py` runner, multi-OS CI, an exception
  hierarchy with actionable messages, logging, config validation, **normalized
  source files written to disk**, cache schema versioning, and a benchmark harness.
- **Docs**: README, internal architecture doc, a security policy, and this docs
  site.
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
- **Interfaces**: a local **React workbench** (`talamus ui`, `ui` extra) served by
  FastAPI and opened in pywebview by default, with `--web` for a browser; the MCP
  server gains an **`overview`** tool (cached domain map, no LLM cost).
- **Polish**: `talamus --version`; `--limit` on `search`/`recall`; **PEP 561**
  `py.typed` so SDK consumers get type hints; folder ingest now **reports failed files**
  instead of dropping them silently; clear messages when the engine returns empty output;
  the UI surfaces engine errors instead of hanging, and renders wikilinks with spaces.

### Changed

- Package `kortex` → `talamus`; CLI `kortex` → `talamus`; config `kortex.json` →
  `talamus.json`; cache `.kortex/` → `.talamus/`; env `KORTEX_*` → `TALAMUS_*`.
