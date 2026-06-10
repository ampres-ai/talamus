# Commands

Run `talamus` with no arguments for a status panel, or `talamus <command> -h` for
options. Most commands accept the [global flags](#global-flags) below.

## Setup & health

| Command | What it does |
| --- | --- |
| `talamus init [--engine E]` | Create a brain here; auto-detects your LLM engine (override with `--engine`). |
| `talamus demo` | Create a small example brain to try instantly (no LLM needed). |
| `talamus status` | Check the brain layout is intact. |
| `talamus doctor` | Health check: brain path, engine on PATH, cache freshness, note count, overview state. |
| `talamus quickstart` | Print the essential commands. |

## Knowledge

| Command | What it does |
| --- | --- |
| `talamus ingest <file\|dir\|url>` | Turn a document, folder, or URL into source-grounded concept notes (PDF/DOCX/HTML/Markdown/text). |
| `talamus ask "<question>"` | Cited answer composed from your brain. |
| `talamus overview [--rebuild]` | Show the hierarchical domain map induced from the graph. |
| `talamus search "<query>" [--limit N]` | List relevant notes (token-cheap). |
| `talamus read "<title>"` | Print one note. |
| `talamus recall "<question>" [--limit N]` | Retrieve the relevant context (for agents to reason over). |
| `talamus neighbors "<concept>"` | Show a concept's typed connections. |
| `talamus history "<title>" [--as-of T]` | Show a note's past versions (or the one current at time T). |
| `talamus reindex` | Fold hand-edits to the Markdown notes back into the indexes. |
| `talamus remember --transcript <f> [--diff <f>]` | Capture an agent session into notes. |

## Curate & verify

| Command | What it does |
| --- | --- |
| `talamus consolidate [--apply]` | Find (and optionally merge) duplicate concepts, across languages. |
| `talamus verify "<title>" [--apply]` | Check a note against its preserved source; optionally apply the correction. |
| `talamus relations [--prune MIN]` | List typed relations, or prune those below a confidence. |
| `talamus eval --cases <f.json> [-k N]` | Measure retrieval quality (recall@k / precision@k / MRR) on your own cases. |

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

## Jobs & review

| Command | What it does |
| --- | --- |
| `talamus jobs [list]` | List long-running jobs (scan/ingest/verify/...). |
| `talamus jobs status\|logs\|cancel\|resume <id>` | Inspect, cancel (cooperative, never corrupts notes) or resume a job. |
| `talamus review [list] [--all]` | Pending decisions (corrections, duplicates, ontology candidates, ...). |
| `talamus review show\|apply\|reject <id> [--reason R]` | Decide an item; rejections stay logged, never deleted. |

## Integrations

| Command | What it does |
| --- | --- |
| `talamus mcp install` | Write/merge `.mcp.json` for Claude Code / Cursor / Desktop. |
| `talamus hook` | Print the Claude Code `SessionEnd` capture-hook config. |
| `talamus hook-run` | Run the capture hook (reads the hook JSON on stdin). |
| `talamus completion [bash\|zsh]` | Print a shell completion script. |
| `talamus ui` | Launch the native desktop/web app (needs the `ui` extra). |

## Global flags

- `--root <dir>` — use an explicit brain directory.
- `--brain <name>` — use a named global brain under `TALAMUS_HOME`.
- `--global` — use the default global brain.
- `--json` — machine-readable output (read commands).
- `--verbose` — verbose diagnostics to stderr.

See **[Configuration](configuration.md)** for how a brain is resolved when no flag is given.
