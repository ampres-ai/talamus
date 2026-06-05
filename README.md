# Kortex

Kortex is a local-first knowledge compiler with graph-first retrieval for AI
agents and humans.

It turns source material (documents, notes, and — soon — agent work sessions)
into source-grounded notes, builds a lightweight graph as the routing index, and
lets agents read the real Markdown files before answering with citations.

## Status

Early development, on the `feat/traguardo-1-text-loop` branch. Working today:

- `kortex init` — create a brain (human-readable `notes/` + managed `.kortex/`)
- `kortex ingest <file>` — turn text/Markdown into source-grounded concept notes
  via LLM extraction (claude-cli by default), with provenance and resolved wikilinks
- `kortex ask "<question>"` — cited answer, graph-first with BM25 fallback
- `kortex reindex` — fold hand-edits to the Markdown notes back into the index
- a read-only **MCP server** so AI agents can read from the brain

Planned next: agent-session capture (hook + write tools), PDF/OCR sources, the
self-emerging ontology, and a local UI.

## Development

Run tests:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

Smoke test the CLI (note: `ingest`/`ask` call an LLM, by default `claude-cli`):

```powershell
$brain = "C:\dev\kortex-brain"
$env:PYTHONPATH="src"
python -m kortex.cli init --root $brain
python -m kortex.cli ingest "C:\path\to\a\note.md" --root $brain
python -m kortex.cli ask "a question about the note" --root $brain
```

## Connect to Claude Code (MCP)

Kortex exposes a read-only MCP server so an agent can search and read your brain
during a session. It needs the optional `mcp` extra:

```powershell
pip install "kortex[mcp]"
```

Then register it in Claude Code's `.mcp.json` (point `--root` at your brain):

```json
{
  "mcpServers": {
    "kortex": {
      "command": "kortex-mcp",
      "args": ["--root", "C:\\dev\\kortex-brain"]
    }
  }
}
```

Tools exposed: `search` (find relevant notes), `read_note` (read one note),
`recall` (get the relevant context for a question — the agent reasons over it).

Some local desktop clients prefer HTTP over stdio: start the server with
`kortex-mcp --http --root <brain>` (binds `127.0.0.1:8000`, stays on your machine).

> Running from source (not pip-installed)? Use
> `"command": "python", "args": ["-m", "kortex.mcp_server", "--root", "<brain>"]`
> with `PYTHONPATH=src` in the server's environment.

## Retrieval Principle

The graph is an index, not source truth. Kortex uses the graph to route a
question to candidate notes, then reads the real Markdown files before answering.

## License

Apache-2.0.
