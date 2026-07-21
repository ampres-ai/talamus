# Talamus MCP bundle

This directory builds the local MCPB artifact published to Smithery. The bundle uses
the cross-platform UV runtime and installs the matching `talamus[mcp]` release from
PyPI; it does not embed a private service or a second implementation.

MCPB artifacts follow a separate post-release cycle. Each bundle pins a Talamus
version that is already published on PyPI so `uv.lock` can record the registry's
immutable hashes. A core source tag can therefore contain the previous MCPB release;
the bundle is bumped, relocked, and republished immediately after the new core wheel
is available.

From the repository root:

```bash
uv lock --directory packaging/mcpb
npx --yes @anthropic-ai/mcpb pack packaging/mcpb talamus-1.0.3.mcpb
```

Before publishing, validate the archive with the same CLI and smoke-test the launcher
against a temporary brain directory.

Smithery's current CLI does not yet map the MCPB 0.4 `uv` runtime to its registry
runtime enum, and its server card requires complete tool schemas. Build the equivalent
compatibility artifact with:

```bash
python scripts/build_smithery_mcpb.py talamus-1.0.3-smithery.mcpb
```

That artifact labels the registry runtime as Python, keeps `uv` as the actual launch
command, and copies the exact input/output schemas exposed by FastMCP. The canonical
MCPB remains the standards-first UV bundle above.
