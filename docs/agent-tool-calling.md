# Talamus Agent Tool Calling Guide

Agents should prefer the MCP server when available: it exposes read tools for
grounded context and write tools that preserve review/provenance rules.

## MCP server

```bash
talamus mcp install
talamus-mcp --root .                 # stdio
talamus-mcp --http --host 127.0.0.1 --port 8000
```

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
| `remember(text, scope="project")` | Save an important session insight into the project or central brain. |
| `ingest_text(text, name="insight", scope="project")` | Compile selected text into notes without the worth-remembering gate. |
| `propose_note(text, reason="")` | Put uncertain knowledge into the review queue instead of writing it directly. |
| `review_list()` | List pending review decisions. |
| `review_apply(item_id)` | Apply a review item while preserving history. |
| `review_reject(item_id, reason="")` | Reject a review item and keep the decision logged. |

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
