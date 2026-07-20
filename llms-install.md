# Install Talamus for an MCP client

This guide is for coding agents installing the public Talamus release for a
user. Prefer PyPI over cloning the repository. Talamus requires Python 3.11 or
newer and uses stdio for its local MCP transport.

## 1. Confirm the target

Ask the user which project directory should own the Talamus brain. Use its
absolute path as `<project-root>` below. Do not enable session capture or make
LLM-backed calls without the user's explicit consent.

## 2. Install the release

```bash
pipx install "talamus[mcp]"
```

If `pipx` is unavailable, install it with the platform's supported package
manager. Do not silently replace or upgrade the user's Python installation.

## 3. Initialize the local brain

Initialize only the selected project; this does not install hooks or edit an
MCP client configuration:

```bash
talamus init --root "<project-root>"
```

Do not substitute `talamus setup`: that guided command also connects detected
clients. The user can enable the session-capture hook separately with
`talamus hook --install` after explicitly approving transcript and git-diff
capture.

## 4. Configure the MCP client

For a client that accepts standard MCP JSON, add this server entry:

```json
{
  "mcpServers": {
    "talamus": {
      "command": "talamus",
      "args": ["mcp", "serve", "--root", "<project-root>"]
    }
  }
}
```

Replace `<project-root>` with the absolute path selected in step 1. Preserve
all unrelated entries when editing an existing MCP configuration.

Talamus can configure supported clients itself after the user approves the
configuration change:

```bash
talamus mcp install --agent auto
```

Use `--agent claude`, `cursor`, `codex`, `opencode`, or `all` only when the
target is known. For clients not covered by that command, use the standard JSON
entry above.

## 5. Verify the connection

Start or reload the MCP client and verify that it can initialize the server and
list Talamus tools. A healthy installation exposes tools including `search`,
`read_note`, `recall`, `remember`, `propose_note`, and `review_list`.

Plain search and recall are local. `ask`, smart search, ingestion, verification,
and session compilation can invoke the configured LLM engine; obtain the
user's consent before making calls that may consume a paid quota.

## Troubleshooting

- `talamus doctor` reports environment and brain configuration problems.
- `talamus mcp serve --root "<project-root>"` starts the stdio server directly;
  it is expected to keep running while the MCP client is connected.
- The project documentation is at <https://ampres-ai.github.io/talamus/>.
- Report installation problems at
  <https://github.com/ampres-ai/talamus/issues/new/choose>.
