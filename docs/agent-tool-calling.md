# Talamus Agent Tool Calling Guide

Agents should prefer the MCP server when available: it exposes read tools for
grounded context. Write tools preserve review/provenance rules and are disabled
unless the user grants an explicit capability when starting the server.

## MCP server

```bash
talamus mcp install
talamus mcp serve --root .           # stdio
talamus-mcp --http --host 127.0.0.1 --port 8000
```

All three commands are read-only by default. Generated configurations include
`--read-only` so the capability is visible during review. Opt in deliberately:

```bash
talamus mcp install --enable-writes
talamus mcp serve --root . --enable-writes
talamus-mcp --root . --enable-writes --enable-central-writes
```

`--enable-writes` permits project-brain mutations. Central-brain mutations need
both flags; `--enable-central-writes` alone is rejected. Invalid scope aliases,
missing central brains, and traversal-shaped review IDs fail before any
mutation. Write-tool responses are structured objects with `ok`, `code`,
`message`, and, for capability denials, `required_flags`.

## MCP tools

| Tool | Purpose |
| --- | --- |
| `search(query, smart=False)` | Find relevant notes by title and summary; `smart=True` adds cached LLM query expansion. |
| `read_note(title, as_of="")` | Read the full Markdown note, optionally as it existed at a past time. |
| `ask(question)` | Get a cited answer from the configured brain. |
| `verify(title)` | Check one note against its preserved source and propose a correction if needed. |
| `recall(question)` | Return raw relevant note context for the agent to reason over. |
| `overview()` | Show the domain map for orientation. |
| `neighbors(concept)` | Show typed graph/ontology neighbors for a concept. |
| `history(title)` | List past versions of a note. |
| `sources(title)` | Show recorded provenance for a note. |
| `ontology_status()` | Report schema version, type counts, and typed-edge coverage. |
| `remember(text, scope="project")` | Save an important session insight; needs `--enable-writes`, plus `--enable-central-writes` for `scope="central"`. |
| `ingest_text(text, name="insight", scope="project")` | Compile selected text into notes; uses the same capability split as `remember`. |
| `propose_note(text, reason="")` | Put uncertain knowledge into the review queue; needs `--enable-writes`. |
| `review_list()` | List pending review decisions. |
| `review_apply(item_id)` | Apply a review item while preserving history; needs `--enable-writes`. |
| `review_reject(item_id, reason="")` | Reject a review item and keep the decision logged; needs `--enable-writes`. |

Every runtime tool includes MCP `ToolAnnotations` for display title, read-only,
destructive, idempotent, and open-world behavior. The hints are deliberately
conservative:

| Behavior | Tools |
| --- | --- |
| Read-only, local, repeatable | `read_note`, `recall`, `overview`, `neighbors`, `history`, `sources`, `ontology_status`, `review_list` |
| Read-only but may call the configured engine | `ask`, `verify` |
| May update cache and call the configured engine | `search` when `smart=True` |
| Writes or merges notes through the configured engine | `remember`, `ingest_text` |
| Adds a local review proposal | `propose_note` |
| Resolves local review state | `review_apply`, `review_reject` |

Because MCP annotations apply to a tool rather than one argument combination,
`search` advertises the most capable `smart=True` path even though its default
lexical path is local and read-only.

## CLI equivalents

When MCP is unavailable, wrap these commands as tools:

| Command | Purpose |
| --- | --- |
| `talamus search "<query>" [--smart]` | Find candidate notes. |
| `talamus read "<title>" [--as-of T]` | Read real note content before answering. |
| `talamus recall "<question>"` | Retrieve context without spending an answer call. |
| `talamus ask "<question>" [--as-of T] [--trace]` | Get a cited answer and optionally inspect the route. |
| `talamus verify "<title>"` | Check one note against source provenance. |

The graph and search indexes are routing aids, not answer sources. Agents should
answer from `read_note`, `recall`, or `ask` output and keep citations.
