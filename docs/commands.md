# Commands

Run `talamus` with no arguments for a status panel, or `talamus <command> -h` for
options. Most commands accept the [global flags](#global-flags) below.

## Four ways to query your brain — and what each one costs

New to Talamus? These four commands look similar but do different jobs. The
price that matters is **LLM calls** (they consume your subscription or your
local model's time) and **tokens** (the amount of text sent to the LLM — what
subscriptions actually meter).

| Command | What you get | LLM calls | Speed | Use it when |
| --- | --- | --- | --- | --- |
| `search "q"` | a ranked list of matching notes | **0** | instant | you know roughly what you're looking for |
| `search "q" --smart` | the same list, but the LLM rewrites your query first (cached) | 1 the first time, 0 on repeats | ~seconds once | you only remember the *idea*, not the words |
| `recall "q"` | the full text of the relevant notes, raw | **0** | instant | you are an **agent** and want material to reason over |
| `ask "q"` | a written answer **with citations** and honest "I don't know" | 3–4 | ~seconds | you want an answer, not a reading list |

How much does an `ask` cost in tokens? Ask it: `talamus ask "q" --trace` prints
the exact context tokens sent (the workbench shows it as *cost* on every
answer). Measured on a real 212-note brain, a targeted answer reads ~2,600
tokens of context — **~98% less** than the alternative of pasting the whole
knowledge base into a chat (~113,500 tokens, growing with every note you add,
until it no longer fits at all). That is the point of a brain: the same LLM you
already use, but pointed at exactly the right three pages — with sources —
instead of the whole shelf or (worse) its own memory of the training data.

## Setup & health

| Command | What it does |
| --- | --- |
| `talamus setup [--engine E] [--capture ask\|yes\|no] [--verify-engine]` | One-command onboarding: brain + engine + MCP + the capture hook (installed only with your consent). In a terminal the engine is probed with one tiny live call and any failure comes with the exact fix. |
| `talamus init [--engine E] [--scan] [--profile docs\|code\|all]` | Create a brain here; auto-detects your LLM engine. `--scan` shows the repo scan plan after init. |
| `talamus demo` | Create a small example brain to try instantly (no LLM needed). |
| `talamus status` | Check the brain layout is intact. |
| `talamus doctor` | Health check: brain path, engine on PATH, cache freshness, note count, overview state. |
| `talamus curator [--fix] [--deep]` | The Curator's health pass over EVERY registered brain: pending reviews, captures waiting for retry, ontology candidates, stale caches — one readable report, zero LLM calls. `--fix` applies the mechanically safe repairs (rebuilding stale derived caches); `--deep` also scans provenance (still no LLM, slower on big brains). |
| `talamus quickstart` | Print the essential commands. |

## Knowledge

| Command | What it does |
| --- | --- |
| `talamus ingest <file\|dir\|url> [--yes]` | Turn a document, folder, or URL into source-grounded concept notes (PDF/DOCX/HTML/Markdown/text). Large multi-chunk ingests estimate first and require `--yes`. |
| `talamus scan [dir] [--dry-run\|--yes\|--background]` | Compile an existing repository: plan first (zero cost), then execute as a resumable job. `--profile docs\|code\|all`, `--max-files N`, `--include GLOB`, `--exclude GLOB`, respects `.gitignore`, excludes vendor/caches/lockfiles/secret files, **redacts likely secrets** and stops for approval (`--allow-secrets`). Code becomes module/API digests, not prose. |
| `talamus ask "<question>"` | Cited answer composed from your brain. |
| `talamus overview [--rebuild]` | Show the hierarchical domain map induced from the graph. |
| `talamus search "<query>" [--limit N]` | List relevant notes (token-cheap, instant). |
| `talamus search "<query>" --smart [--passes N]` | Same, but the LLM expands the query first (cached) — finds vague/paraphrased queries the plain search misses. `--passes N` unions N fresh expansion samples (N LLM calls, uncached) to smooth expansion variance. |
| `talamus read "<title>"` | Print one note. |
| `talamus recall "<question>" [--limit N]` | Retrieve the relevant context (for agents to reason over). |
| `talamus neighbors "<concept>"` | Show a concept's typed connections. |
| `talamus history "<title>" [--as-of T]` | Show a note's past versions (or the one current at time T). |
| `talamus timeline "<title>"` | Both timelines: transaction history (when Talamus changed the record) and valid-time claims (when facts were true). |
| `talamus read "<title>" --as-of T` / `talamus ask "<q>" --as-of T` | The note / the answer as the brain was at time T (accepts `2026`, `2026-01`, `2026-01-15`, full ISO; partial dates = end of period). |
| `talamus reindex` | Fold hand-edits to the Markdown notes back into the indexes. |
| `talamus watch [dir] [--cap N] [--interval S] [--once]` | Watch a folder: dropping a supported file in makes it notes automatically (llm-wiki style). Starting the watch IS the consent; a daily cap (default 50 files) bounds the spend, unchanged files are hash-skipped, multi-chunk documents are left for an explicit `talamus ingest --yes`, and the brain's own output is never re-ingested. |
| `talamus remember --transcript <f> [--diff <f>]` | Capture an agent session into notes. |
| `talamus import-vault <dir>` | Import a Markdown/Obsidian vault 1:1 — **no LLM call**: titles, tags, aliases and `[[wikilinks]]` preserved, wikilinks become graph edges, idempotent re-runs. A Notion markdown export imports the same way. |

## Curate & verify

| Command | What it does |
| --- | --- |
| `talamus consolidate [--apply]` | Find (and optionally merge) duplicate concepts, across languages. |
| `talamus enrich [--yes]` | Add symptom/vocabulary phrasings to `retrieval_text`; estimates first and runs only with `--yes`. |
| `talamus verify "<title>" [--apply]` | Check a note against its preserved source; optionally apply the correction. |
| `talamus verify --all \| --stale \| --source S` | Batch: provenance health (missing/changed source, low confidence — no LLM with `--stale`) + content checks; proposed corrections land in the **review queue**, never overwrite silently. |
| `talamus supersede "<old>" --by "<new>"` | The bitemporal handover: mark a note as replaced by a newer one. **Nothing is deleted** — the old note keeps its prose and history (`--as-of` still reaches it); its open claims close, a `supersedes` edge enters the graph, and default answers read only the successor. |
| *(automatic at ingest)* | When a newly ingested note looks like a replacement of an existing one, Talamus judges it (one LLM call): confident verdicts apply the handover automatically and say so; uncertain ones land in the review queue. Disable with `TALAMUS_SUPERSEDES_DETECTION=0`. |
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
| `talamus mcp install [--agent auto\|claude\|cursor\|codex\|opencode\|openclaw\|all]` | Connect agents in one command. OpenClaw is registered through `openclaw mcp set`, pins this project brain with `--root`, and starts with read-oriented tools; LLM-backed and mutating tools remain opt-in. Auto detects installed CLIs. |
| `talamus hook` | Print the Claude Code `SessionEnd` capture-hook config. |
| `talamus hook --install` | Write the hook into `.claude/settings.json` (merges, idempotent). |
| `talamus hook --retry` | Replay captured sessions the engine failed on (a hit usage limit parks the capture under `.talamus/pending/` instead of losing it; entries stay until they succeed — `doctor` reminds you). |
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
