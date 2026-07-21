# Talamus Memory plugin

Give Cursor, Claude Code, GitHub Copilot CLI, or goose durable, source-grounded
memory for the current project. Cursor receives a dedicated CLI-first skill;
the other plugin formats keep the bundled skill and local MCP launcher.

## What installation does

- Registers the relevant `talamus-memory` skill for the host.
- Cursor does not start an MCP server or install Talamus. Its skill uses
  consented, pinned `uvx` commands for CLI access from the active workspace.
- Claude Code, GitHub Copilot CLI, and goose retain their existing local MCP
  launchers.
- Does not install a session-capture hook, read transcripts, initialize a brain,
  or send project content anywhere by itself.

`uv` must be available on `PATH`. See the official installation instructions at
<https://docs.astral.sh/uv/getting-started/installation/>.

## Data and consent

Talamus stores its brain as inspectable Markdown plus derived local indexes in
the project selected by the host agent. Read-only lexical retrieval does not
need an LLM. Smart search, cited answer generation, ingestion, verification,
and memory writes can call the LLM provider configured by the user. The bundled
skill requires explicit consent before those operations and before any session
capture or hook installation.

## Cursor: CLI-first access

The Cursor skill first confirms the resolved brain with `talamus where --json`
and keeps ordinary recall on read-only commands such as `search`, `recall`,
`read`, and `history`. Before the first `uvx` run, it discloses that the pinned
package may be downloaded into `uv`'s cache and asks for consent. It never runs
`ask`, smart search, a write, or a persistent installation without explicit
approval.

## Initialize a project brain

If the project does not have a Talamus brain yet, review the change and run from
the project root:

```bash
uvx --from "talamus[mcp]==1.0.3" talamus setup --capture ask
```

For a minimal brain without agent configuration or a capture hook:

```bash
uvx --from "talamus[mcp]==1.0.3" talamus init
```

Cursor's plugin does not provide MCP registration. Initialization and MCP setup
are separate, consented actions.

## Cursor: optional project-scoped MCP

After explicit approval for a persistent tool install and a workspace config
change, install the pinned package and configure Cursor from the initialized
workspace root:

```bash
uv tool install "talamus[mcp]==1.0.3"
talamus mcp install --agent cursor
```

The skill reads `.cursor/mcp.json` before and after the command, preserves every
existing server, and verifies that Talamus's `--root` is absolute and matches
the workspace. Do not run the installer itself through `uvx`: version 1.0.3
writes a bare `talamus-mcp` launcher, which must remain available after setup.

## Development validation

From the Talamus repository root:

```bash
claude plugin validate ./plugins/talamus-memory --strict
python -m unittest tests.test_agent_plugin_package -v
uvx --from "talamus[mcp]==1.0.3" talamus-mcp --help
```

The component bundle is designed for both the Claude Code plugin format and
GitHub Copilot CLI's compatible plugin loader. The manifest is present in both
`.claude-plugin/plugin.json` and `plugin.json` because the two marketplace
validators currently recognize different canonical locations; repository tests
keep their content identical. goose uses the repository-level
`.goose-plugin/plugin.json`, which points to this skill and supplies a
project-relative MCP launcher without changing either compatible manifest.
Cursor uses `.cursor-plugin/plugin.json`; the repository-level
`.cursor-plugin/marketplace.json` points Cursor at this bundle. Its manifest
selects the dedicated `cursor-skills/` directory and intentionally contains no
bundled MCP server, avoiding plugin-cache working-directory errors.
