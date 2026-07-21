# Talamus

![Talamus — Memory that survives the session.](assets/talamus-social-preview.png)

**Local-first, source-grounded memory that you and your AI agents share.**

Talamus turns documents, repositories, URLs, and consented agent sessions into
durable Markdown knowledge. It retrieves that knowledge with citations and
bitemporal history, on your machine and with the LLM engine you already use.

[Install in 60 seconds](quickstart.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/ampres-ai/talamus){ .md-button }

```bash
pipx install "talamus[mcp]"
talamus setup
```

No account or hosted service is required. Plain search and recall are local and
free; operations that invoke an LLM remain explicit.

## See memory survive a fresh session

![A completed agent session becomes cited, local memory for the next one.](assets/talamus-demo.gif)

Talamus exposes 16 MCP tools for Claude Code, Cursor, Codex, OpenCode, and OpenClaw, while
the same brain stays readable as ordinary Markdown plus a local SQLite/FTS5
index.

## What makes it different

- **Time** — inspect what the brain knew at an earlier date with `--as-of`,
  `history`, and `timeline`.
- **Meaning** — induce and review an evidence-backed ontology instead of
  imposing a fixed folder tree.
- **Verifiability** — retain source provenance, cite retrieved notes, and gate
  proposed corrections behind review.
- **Local-first control** — keep the core usable without a cloud account,
  hosted database, or hidden paid call.

The [measured benchmarks](benchmarks.md) publish both wins and losses, with every
public number traced to a committed result artifact.

## Where to go next

- **[Quickstart](quickstart.md)** — install and try it in 10 minutes.
- **[Local-first agent memory](local-first-agent-memory.md)** — evaluate the
  architecture, trade-offs, and no-LLM demo.
- **[Agent install guide](https://github.com/ampres-ai/talamus/blob/main/llms-install.md)** — configure an agent without hidden side effects.
- **[Commands](commands.md)** — browse the full `talamus` CLI reference.
- **[Benchmarks](benchmarks.md)** — inspect the measured numbers and artifacts.
- **[Architecture](architecture.md)** — see how the local-first pieces fit together.
- **[GitHub](https://github.com/ampres-ai/talamus)** — report an issue, contribute, or star the project.
