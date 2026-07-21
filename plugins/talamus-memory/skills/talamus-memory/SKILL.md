---
name: talamus-memory
description: Use Talamus as durable, local-first memory through its MCP tools. Use when an agent needs cited context across sessions, source-grounded project recall, note history, provenance checks, reviewed memory writes, or help initializing and diagnosing a Talamus brain.
---

# Talamus Memory

Use the bundled Talamus MCP server to retrieve and maintain inspectable project
memory. Prefer deterministic retrieval, preserve citations, and obtain consent
before any operation that can call an LLM, change memory, or capture a session.

## Runtime and safety contract

- The plugin launches `talamus[mcp]==1.0.3` through `uvx` for the active project.
  The first start may download the pinned package into the local `uv` cache; it
  does not install Talamus persistently.
- Never install a capture hook or read a transcript without explicit consent.
- Treat smart search, answer generation, ingestion, verification, and all
  memory writes as potentially paid LLM operations. State the intended action
  and obtain approval unless the user explicitly requested that exact action.
- Never apply or reject a review item automatically. Show the proposal and wait
  for the user's decision.
- Never expose secrets from project files, configuration, environment
  variables, transcripts, or `.talamus/logs`.
- Preserve Talamus citations and distinguish retrieved evidence from model
  inference.

## Retrieve before generating

Start with the read-only, non-LLM MCP tools:

1. Use `overview` to understand the brain's domains.
2. Use `recall` for compact context relevant to a question.
3. Use `search` with smart mode disabled for lexical retrieval.
4. Use `read_note` for the full cited note.
5. Use `neighbors`, `history`, and library or ontology inspection when the user
   needs relationships, earlier versions, or provenance detail.

If the requested time matters, pass the explicit historical boundary rather
than answering from the current note. If retrieval is empty, say so; do not
invent remembered facts.

Use smart search or the `ask` tool only after the user approves the possible
LLM call. Return the cited sources alongside any synthesis.

## Initialize or diagnose a brain

If the MCP tools report that no brain exists, ask whether memory should belong
to the current project. After approval, initialize from the project root:

```bash
uvx --from "talamus[mcp]==1.0.3" talamus setup --capture ask
```

Use `talamus init` through the same `uvx --from` prefix for minimal setup without
agent configuration or a hook. Use `talamus doctor`, `talamus where`, and
`talamus status` through that prefix for diagnostics. A persistent `uv tool` or
`pipx` installation is optional and requires separate approval.

## Add knowledge deliberately

For a source or raw memory write, summarize the scope and likely LLM activity
before calling a mutating MCP tool. For repository ingestion, use the CLI to
preview first:

```bash
uvx --from "talamus[mcp]==1.0.3" talamus scan . --dry-run --profile docs
```

Run the approved ingestion only after showing the preview. Never allow secrets
without explicit approval. After a write, report which brain changed, which
sources were processed, which notes changed, and which items need review.

## Verify and curate

Use read-only provenance and review-list tools first. Show proposed corrections
before applying or rejecting them. If manual note edits made the derived index
stale, ask before running a reindex.

Before bulk curation, relocation, or destructive maintenance, create a portable
backup with the CLI:

```bash
uvx --from "talamus[mcp]==1.0.3" talamus export brain.zip
```

End the workflow with the active project path, the tools or commands actually
used, any LLM or capture activity, the evidence retrieved or changed, and the
safest next action.
