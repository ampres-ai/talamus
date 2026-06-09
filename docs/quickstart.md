# Talamus — Quickstart (10 minutes)

Local-first knowledge that both you and your AI agents can read and write.

## 1. Install

```bash
pipx install talamus            # or: pip install talamus
```

Optional: `pipx install "talamus[mcp]"` for the agent MCP server.

## 2. Try it instantly (no setup, no LLM)

```bash
talamus demo                    # creates a small example brain here
talamus search "embedding"
talamus neighbors "Embedding"
talamus read "Embedding"
```

## 3. Your own brain

```bash
talamus init                    # detects your LLM engine, creates a brain here
talamus ingest notes.md         # document -> linked concept-notes (with sources)
talamus ask "how does X work?"  # cited answer from your brain
```

`talamus` (no args) shows brain status and next steps. `talamus doctor` runs a health check.

## 4. Choose your engine

Talamus runs on what you already have — set it in `talamus.json` (or `TALAMUS_LLM_PROVIDER`):

- `claude-cli` — your Claude subscription (default if `claude` is on PATH)
- `ollama` — a local model (`TALAMUS_LLM_MODEL=llama3`), fully offline
- `anthropic-api` — the Anthropic API (`ANTHROPIC_API_KEY`)

## 5. Use it from agents (MCP)

```bash
talamus mcp install             # writes .mcp.json for Claude Code / Cursor / Desktop
```

Agents can then `search` / `read_note` / `recall` / `remember` against your brain. To
capture your work sessions automatically:

```bash
talamus hook                    # prints the Claude Code SessionEnd hook to add
```

## 6. Browse like a wiki (Obsidian)

Open the `notes/` folder as an Obsidian vault: notes cross-link with `[[wikilinks]]`,
so you can navigate the knowledge by hovering and clicking.

## Global vs project brains

By default Talamus uses the nearest **project** brain (a folder with `talamus.json`,
searched upward), else a personal **global** brain under `~/talamus` (`TALAMUS_HOME`).
Force one with `--global` or `--brain <name>`; `talamus where` shows the active brain,
`talamus brains` lists the global ones.

## Move or back up a brain

```bash
talamus export brain.zip
talamus import brain.zip --root ./restored
```
