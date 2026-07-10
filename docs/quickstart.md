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
talamus ingest report.pdf       # PDF / DOCX / HTML / Markdown / URL -> linked concept-notes
talamus overview                # induce the domain map (handy as the brain grows)
talamus ask "how does X work?"  # cited answer from your brain
```

`talamus` (no args) shows brain status and next steps. `talamus doctor` runs a health check.

## 4. Choose your engine

Talamus runs on what you already have — set it in `talamus.json` (or `TALAMUS_LLM_PROVIDER`):

- `claude-cli` — your Claude subscription (default if `claude` is on PATH)
- `codex-cli` — your ChatGPT subscription through Codex
- `antigravity-cli` — Google Antigravity (`agy`), your Gemini subscription
- `opencode` — opencode, with whatever providers you configured in it
- `ollama` — a local model (`TALAMUS_LLM_MODEL=llama3`), fully offline
- `anthropic-api` — the Anthropic API (`ANTHROPIC_API_KEY`)

(The old standalone `gemini-cli` still works if you have it installed, but
Google has deprecated it — use `antigravity-cli` instead.)

## 5. Use it from agents (MCP)

```bash
talamus mcp install             # one command: Claude Code + Cursor + codex (auto-detected)
```

Claude Code reads the project `.mcp.json`, Cursor its `.cursor/mcp.json`,
and codex gets one global registration (`codex mcp add talamus`) that resolves
the right brain from whatever project codex runs in.

Agents can then `search` / `read_note` / `recall` / `overview` / `neighbors` / `remember`
against your brain. To capture your work sessions automatically:

```bash
talamus hook --install          # writes the Claude Code SessionEnd hook (asks nothing else)
talamus hook                    # or just print the snippet to add by hand
```

The hook sends Talamus the session transcript and the git diff when a session
ends; only sessions that pass the worth-remembering gate become notes, and every
decision is logged to `.talamus/logs/capture.log`. `talamus setup` proposes this
hook and installs it only if you consent (`--capture yes|no|ask`).

A session is never lost to engine trouble: if your LLM hits its usage limit
during a capture, the session is parked locally and `talamus hook --retry`
replays it once the limit resets (`talamus doctor` reminds you when captures
are waiting).

## 6. Browse like a wiki (Obsidian)

Open the `notes/` folder as an Obsidian vault: notes cross-link with `[[wikilinks]]`,
so you can navigate the knowledge by hovering and clicking.

Prefer a dedicated app? Install the UI extra and launch the local React web
workbench. It opens in a pywebview window by default; use `--web` for a browser.
The workbench has 10 views: Home, Ask, Graph, Library, Import, Ontology, Review,
Brains, Connect, and System.

```bash
pip install "talamus[ui]"
talamus ui                      # pywebview window
talamus ui --web --port 8760    # browser, custom port
```

## Coming from Obsidian or Notion?

Import your existing vault 1:1 — instant, free, no LLM call:

```bash
talamus import-vault ~/my-vault
```

Titles, tags, aliases and `[[wikilinks]]` are preserved (links become graph
edges), and re-running skips unchanged notes. A Notion **markdown export**
imports the same way. Your notes are searchable immediately.

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
