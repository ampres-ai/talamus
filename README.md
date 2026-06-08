# Talamus

Talamus is a local-first knowledge compiler with graph-first retrieval for AI
agents and humans.

It turns source material (documents, notes, and — soon — agent work sessions)
into source-grounded notes, builds a lightweight graph as the routing index, and
lets agents read the real Markdown files before answering with citations.

## Status

Early development, on the `feat/traguardo-1-text-loop` branch. Working today:

- `talamus init` — create a brain (human-readable `notes/` + managed `.talamus/`)
- `talamus ingest <file>` — turn text/Markdown into source-grounded concept notes
  via LLM extraction (claude-cli by default), with provenance and resolved wikilinks
- `talamus ask "<question>"` — cited answer, graph-first with BM25 fallback
- `talamus reindex` — fold hand-edits to the Markdown notes back into the index
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
$brain = "C:\dev\talamus-brain"
$env:PYTHONPATH="src"
python -m talamus.cli init --root $brain
python -m talamus.cli ingest "C:\path\to\a\note.md" --root $brain
python -m talamus.cli ask "a question about the note" --root $brain
```

## Connect to Claude Code (MCP)

Talamus exposes a read-only MCP server so an agent can search and read your brain
during a session. It needs the optional `mcp` extra:

```powershell
pip install "talamus[mcp]"
```

Then register it in Claude Code's `.mcp.json` (point `--root` at your brain):

```json
{
  "mcpServers": {
    "talamus": {
      "command": "talamus-mcp",
      "args": ["--root", "C:\\dev\\talamus-brain"]
    }
  }
}
```

Tools exposed: `search` (find relevant notes), `read_note` (read one note),
`recall` (get the relevant context for a question — the agent reasons over it).

Some local desktop clients prefer HTTP over stdio: start the server with
`talamus-mcp --http --root <brain>` (binds `127.0.0.1:8000`, stays on your machine).

> Running from source (not pip-installed)? Use
> `"command": "python", "args": ["-m", "talamus.mcp_server", "--root", "<brain>"]`
> with `PYTHONPATH=src` in the server's environment.

## Capture sessions (Claude Code hook)

Talamus can turn your agent work sessions into notes. Set `TALAMUS_ROOT` to your brain
and register the hook script on Claude Code's `SessionEnd` event (in your settings):

```json
{
  "hooks": {
    "SessionEnd": [
      { "hooks": [ { "type": "command", "command": "python /path/to/talamus/scripts/talamus-session-hook.py" } ] }
    ]
  }
}
```

At session end the hook reads the transcript, captures `git diff`, and calls
`talamus remember` — which compiles the session into source-grounded notes (a
heuristic gate skips trivial sessions). You can also run it by hand:

```powershell
python -m talamus.cli remember --transcript <transcript.jsonl> --diff <changes.diff> --root <brain>
```

## Retrieval Principle

The graph is an index, not source truth. Talamus uses the graph to route a
question to candidate notes, then reads the real Markdown files before answering.

## License

Apache-2.0.
