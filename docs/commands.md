# Commands

Run `talamus` with no arguments for a status panel, or `talamus <command> -h` for
options. Most commands accept the [global flags](#global-flags) below.

## Setup & health

| Command | What it does |
| --- | --- |
| `talamus init [--engine E]` | Create a brain here; auto-detects your LLM engine (override with `--engine`). |
| `talamus demo` | Create a small example brain to try instantly (no LLM needed). |
| `talamus status` | Check the brain layout is intact. |
| `talamus doctor` | Health check: engine on PATH, cache freshness, note count. |
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
| `talamus brains` | List the global brains under `TALAMUS_HOME`. |
| `talamus where` | Print which brain is resolved right now. |
| `talamus export <zip>` | Export the brain to a zip. |
| `talamus import <zip> [--root D]` | Import a brain zip into a directory. |

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
