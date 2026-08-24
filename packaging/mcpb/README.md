# Talamus MCP bundle

Talamus gives AI agents durable, source-grounded memory in a folder you control.
The bundle runs a local MCP server with 16 tools for search, cited recall,
provenance, history, review, and deliberate memory updates. It does not require a
Talamus account or a publisher-operated backend.

## Install

1. Download the signed-off `.mcpb` artifact from the Talamus release or its
   directory listing.
2. Open it with an MCPB-compatible client such as Claude Desktop.
3. Choose the **Talamus brain folder** the server may access.
4. Review the tool permissions before enabling the server.

The first launch uses UV to download the manifest's pinned `talamus[mcp]`
release from PyPI into UV's isolated cache. Talamus then reads and writes only
the selected brain folder unless a tool explicitly selects the separately
configured central brain.

## Try it

These prompts exercise the bundle without assuming hidden data or a hosted
service.

### Find a past decision

> Search this Talamus brain for the storage decision and show the matching note
> summaries.

Expected behavior: `search` performs local lexical retrieval and returns note
titles and summaries. If smart search is explicitly requested, it may use the
user-configured language-model engine and cache the expansion locally.

### Inspect evidence and history

> Read the note "Storage" and show both its sources and its change history.

Expected behavior: `read_note`, `sources`, and `history` read the selected brain
without modifying it or contacting an external service.

### Recall context without an LLM call

> Recall the context for "Why did we choose FTS5?" so I can reason over the raw
> notes myself.

Expected behavior: `recall` returns local note context. It does not call a
language model.

### Save a reviewed insight

> Remember that the team chose WAL mode after the concurrency test.

Expected behavior: after the client obtains approval for a write-capable tool,
`remember` sends the supplied text to the user's configured engine, then writes
the resulting note and provenance into the chosen brain. It can update an
existing note while preserving its history.

### Keep uncertainty in review

> Propose, but do not apply, the claim that the migration finished on Friday.

Expected behavior: `propose_note` adds an item to the local review queue. It does
not change canonical notes. `review_apply` and `review_reject` are separate,
state-changing decisions.

## Permissions and privacy

- Read-only local tools: `read_note`, `recall`, `overview`, `neighbors`,
  `history`, `sources`, `ontology_status`, and `review_list`.
- Tools that may use the user-configured engine: `search` with smart mode,
  `ask`, `verify`, `remember`, and `ingest_text`.
- Tools that modify local state: `search` in smart mode may update its query
  cache; `remember` and `ingest_text` write or merge notes; `propose_note`
  appends to the review queue; `review_apply` and `review_reject` resolve it.
- Talamus has no publisher-operated analytics, telemetry, account, or memory
  backend. Optional engine providers and PyPI/UV operate under their own terms.

Read the full [Talamus privacy policy](https://ampres-ai.github.io/talamus/privacy/)
and [security policy](https://github.com/ampres-ai/talamus/blob/main/SECURITY.md).
Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/ampres-ai/talamus/security/advisories/new).

## Support

- Documentation: https://ampres-ai.github.io/talamus/
- Issues: https://github.com/ampres-ai/talamus/issues
- Source: https://github.com/ampres-ai/talamus

## Build and publish

This directory builds the local MCPB artifact published to Smithery. The bundle
uses the cross-platform UV runtime and installs the matching `talamus[mcp]`
release from PyPI; it does not embed a private service or a second
implementation.

MCPB artifacts follow a separate post-release cycle. Each bundle pins a Talamus
version already published on PyPI so `uv.lock` records immutable registry
hashes. A core source tag can therefore contain the previous MCPB release; the
bundle is bumped, relocked, and republished immediately after the new core wheel
is available.

From the repository root:

```bash
uv lock --upgrade-package talamus --directory packaging/mcpb
uv lock --check --directory packaging/mcpb
mkdir -p dist/mcpb
npx --yes @anthropic-ai/mcpb@2.1.2 validate packaging/mcpb/manifest.json
npx --yes @anthropic-ai/mcpb@2.1.2 pack packaging/mcpb dist/mcpb/talamus-1.1.2.mcpb
npx --yes @anthropic-ai/mcpb@2.1.2 info dist/mcpb/talamus-1.1.2.mcpb
```

Before publishing, smoke-test the launcher against a temporary brain directory.

Smithery's current CLI does not yet map the MCPB 0.4 `uv` runtime to its
registry runtime enum, and its server card requires complete tool schemas. Build
the equivalent compatibility artifact with:

```bash
uv run --frozen --project packaging/mcpb \
  python scripts/build_smithery_mcpb.py dist/mcpb/talamus-1.1.2-smithery.mcpb
npx --yes @anthropic-ai/mcpb@2.1.2 info dist/mcpb/talamus-1.1.2-smithery.mcpb
```

That artifact labels the registry runtime as Python, keeps `uv` as the actual
launch command, includes this user-facing README, and copies the exact
input/output schemas and annotations exposed by the MCP runtime. The canonical
MCPB remains the standards-first UV bundle above.

Smithery publication is not idempotent. Confirm the authenticated session and
publish the compatibility artifact only once for each version:

```bash
npx --yes smithery@1.2.0 auth whoami
npx --yes smithery@1.2.0 mcp publish dist/mcpb/talamus-1.1.2-smithery.mcpb -n ampres-ai/talamus
```
