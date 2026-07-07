# Commands

Run `talamus` with no arguments for a status panel, or `talamus <command> -h` for
options. Most commands accept the [global flags](#global-flags) below.

## Setup & health

| Command | What it does |
| --- | --- |
| `talamus setup [--engine E] [--capture ask\|yes\|no]` | One-command onboarding: brain + engine + MCP + the capture hook (installed only with your consent). |
| `talamus init [--engine E] [--scan] [--profile docs\|code\|all]` | Create a brain here; auto-detects your LLM engine. `--scan` shows the repo scan plan after init. |
| `talamus demo` | Create a small example brain to try instantly (no LLM needed). |
| `talamus status` | Check the brain layout is intact. |
| `talamus doctor` | Health check: brain path, engine on PATH, cache freshness, note count, overview state. |
| `talamus quickstart` | Print the essential commands. |

## Knowledge

| Command | What it does |
| --- | --- |
| `talamus ingest <file\|dir\|url> [--yes]` | Turn a document, folder, or URL into source-grounded concept notes (PDF/DOCX/HTML/Markdown/text). Large multi-chunk ingests estimate first and require `--yes`. |
| `talamus scan [dir] [--dry-run\|--yes\|--background]` | Compile an existing repository: plan first (zero cost), then execute as a resumable job. `--profile docs\|code\|all`, `--max-files N`, `--include GLOB`, `--exclude GLOB`, respects `.gitignore`, excludes vendor/caches/lockfiles/secret files, **redacts likely secrets** and stops for approval (`--allow-secrets`). Code becomes module/API digests, not prose. |
| `talamus ask "<question>"` | Cited answer composed from your brain. |
| `talamus overview [--rebuild]` | Show the hierarchical domain map induced from the graph. |
| `talamus search "<query>" [--limit N]` | List relevant notes (token-cheap, instant). |
| `talamus search "<query>" --smart` | Same, but the LLM expands the query first (cached) — finds vague/paraphrased queries the plain search misses. |
| `talamus read "<title>"` | Print one note. |
| `talamus recall "<question>" [--limit N]` | Retrieve the relevant context (for agents to reason over). |
| `talamus neighbors "<concept>"` | Show a concept's typed connections. |
| `talamus history "<title>" [--as-of T]` | Show a note's past versions (or the one current at time T). |
| `talamus timeline "<title>"` | Both timelines: transaction history (when Talamus changed the record) and valid-time claims (when facts were true). |
| `talamus read "<title>" --as-of T` / `talamus ask "<q>" --as-of T` | The note / the answer as the brain was at time T (accepts `2026`, `2026-01`, `2026-01-15`, full ISO; partial dates = end of period). |
| `talamus reindex` | Fold hand-edits to the Markdown notes back into the indexes. |
| `talamus remember --transcript <f> [--diff <f>]` | Capture an agent session into notes. |
| `talamus import-vault <dir>` | Import a Markdown/Obsidian vault 1:1 — **no LLM call**: titles, tags, aliases and `[[wikilinks]]` preserved, wikilinks become graph edges, idempotent re-runs. A Notion markdown export imports the same way. |

## Curate & verify

| Command | What it does |
| --- | --- |
| `talamus consolidate [--apply]` | Find (and optionally merge) duplicate concepts, across languages. |
| `talamus enrich [--yes]` | Add symptom/vocabulary phrasings to `retrieval_text`; estimates first and runs only with `--yes`. |
| `talamus verify "<title>" [--apply]` | Check a note against its preserved source; optionally apply the correction. |
| `talamus verify --all \| --stale \| --source S` | Batch: provenance health (missing/changed source, low confidence — no LLM with `--stale`) + content checks; proposed corrections land in the **review queue**, never overwrite silently. |
| `talamus relations [--prune MIN]` | List typed relations, or prune those below a confidence. |
| `talamus eval --cases <f.json> [-k N] [--category C]` | Measure retrieval quality (recall@k / precision@k / MRR) on your own cases. |
| `talamus eval --scale [--sizes N,N,N]` | Latency benchmark at growing corpus sizes (persistent index backend). |
| `talamus ask "<q>" --trace` | Explain the route: domains chosen (by stable id), notes read, context tokens, fallbacks. |

## Brains & scoping

| Command | What it does |
| --- | --- |
| `talamus brains [list]` | List the registered brains (registry under `TALAMUS_HOME`). |
| `talamus brains use <name>` | Select the default global brain (used when no project is found). |
| `talamus brains info <name>` | Show one brain's registry record + stats. |
| `talamus brains register <path> [--name N] [--type T]` | Register an existing brain (project/central/archive). |
| `talamus brains rename <old> <new>` / `delete <name>` | Rename / unregister (files on disk are preserved). |
| `talamus brains set <name> --federated true\|false --sensitive true\|false` | Federation & privacy flags. |
| `talamus brains index [status] [--rebuild]` | Build or inspect the local federated index. |
| `talamus brains promote <note> --from A --to B` | Promote a note between brains (id, provenance and history preserved). |
| `talamus where [--json]` | Print which brain is resolved (JSON adds scope + source). |
| `talamus export <zip>` | Export the brain to a zip. |
| `talamus import <zip> [--root D]` | Import a brain zip into a directory. |

`ask` / `search` / `recall` / `overview` accept **`--scope`** (`project-only`, `central-only`,
`project+central`, `all`) and **`--all-brains`** (alias for `--scope all`). Inside a project the
default is `project+central`; from the central brain it is `all` (sensitive brains excluded).
Cross-brain results carry markers (`[central]`, `[project:name]`) and always read the real
notes from the owning brain — the federated index is a pointer index, never source truth.

## Ontology Lab (the emergent type system)

| Command | What it does |
| --- | --- |
| `talamus ontology status` | Schema version, type counts, coverage (share of typed edges). |
| `talamus ontology induce [--min-support N]` | Induce candidate relation types from unexplained surfaces (1 LLM call). |
| `talamus ontology review` | Candidates with support, definitions and real-source examples. |
| `talamus ontology apply <id> [--force]` | Promote to active (thresholds: support ≥ 8 on ≥ 3 notes); re-types the concept map. |
| `talamus ontology reject <id> [--reason R]` | Reject a candidate; the decision is recorded. |
| `talamus ontology deprecate <id> [--reason R]` | Deprecate an active type; types are never deleted. |
| `talamus ontology eval --cases <f> [-k N]` | Retrieval lift: fixed baseline vs active emergent schema. |
| `talamus ontology stability [--runs N]` | Cluster stability (Jaccard) over repeated inductions. |
| `talamus ontology history\|export` | Schema events, full schema JSON. |

## Jobs & review

| Command | What it does |
| --- | --- |
| `talamus jobs [list]` | List long-running jobs (scan/ingest/verify/...). |
| `talamus jobs status\|logs\|cancel\|resume <id>` | Inspect, cancel (cooperative, never corrupts notes) or resume a job. |
| `talamus review [list] [--all]` | Pending decisions (corrections, duplicates, ontology candidates, ...). |
| `talamus review show\|apply <id>` | Inspect or apply an item. |
| `talamus review reject <id> [--reason R]` | Reject an item; rejections stay logged, never deleted. |

## Integrations

| Command | What it does |
| --- | --- |
| `talamus mcp install` | Write/merge `.mcp.json` for Claude Code / Cursor / Desktop. |
| `talamus hook` | Print the Claude Code `SessionEnd` capture-hook config. |
| `talamus hook --install` | Write the hook into `.claude/settings.json` (merges, idempotent). |
| `talamus hook-run` | Run the capture hook (reads the hook JSON on stdin). |
| `talamus completion [bash\|zsh]` | Print a shell completion script. |
| `talamus ui [--web] [--port N]` | Launch the local React workbench (needs the `ui` extra): pywebview window by default, browser with `--web`. |

## Global flags

- `--root <dir>` — use an explicit brain directory.
- `--brain <name>` — use a named global brain under `TALAMUS_HOME`.
- `--global` — use the default global brain.
- `--json` — machine-readable output (read commands).
- `--plain` / `--no-color` — plain output with no ANSI color.
- `--verbose` — verbose diagnostics to stderr.

See **[Configuration](configuration.md)** for how a brain is resolved when no flag is given.
