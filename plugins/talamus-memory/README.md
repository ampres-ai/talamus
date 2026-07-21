# Talamus Memory plugin

Give Claude Code or GitHub Copilot CLI durable, source-grounded memory for the
current project. The plugin combines a consent-aware agent skill with Talamus's
local MCP server.

## What installation does

- Registers the bundled `talamus-memory` skill.
- Starts the local Talamus MCP server for the active project when the plugin is
  enabled.
- Uses `uvx` to run the pinned PyPI package `talamus[mcp]==1.0.3` in an isolated
  cache. The first start may download that package and its dependencies.
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

The plugin itself already provides the MCP registration, so a separate
`talamus mcp install` is not required.

## Development validation

From the Talamus repository root:

```bash
claude plugin validate ./plugins/talamus-memory --strict
uvx --from "talamus[mcp]==1.0.3" talamus-mcp --help
```

The plugin is designed for both the Claude Code plugin format and GitHub
Copilot CLI's compatible plugin loader. The manifest is present in both
`.claude-plugin/plugin.json` and `plugin.json` because the two marketplace
validators currently recognize different canonical locations; repository tests
keep their content identical.
