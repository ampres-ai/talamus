# Talamus MCP bundle

This directory builds the local MCPB artifact published to Smithery. The bundle uses
the cross-platform UV runtime and installs the matching `talamus[mcp]` release from
PyPI; it does not embed a private service or a second implementation.

From the repository root:

```bash
uv lock --directory packaging/mcpb
npx --yes @anthropic-ai/mcpb pack packaging/mcpb talamus-1.0.3.mcpb
```

Before publishing, validate the archive with the same CLI and smoke-test the launcher
against a temporary brain directory.
