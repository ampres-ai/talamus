# Talamus

<!-- mcp-name: io.github.ampres-ai/talamus -->

[![CI](https://github.com/ampres-ai/talamus/actions/workflows/ci.yml/badge.svg)](https://github.com/ampres-ai/talamus/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/talamus)](https://pypi.org/project/talamus/) [![MCP Registry](https://img.shields.io/badge/MCP_Registry-active-5b5bd6)](https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.ampres-ai%2Ftalamus) [![Smithery](https://img.shields.io/badge/Smithery-install-111827)](https://smithery.ai/servers/ampres-ai/talamus) [![skills.sh](https://skills.sh/b/ampres-ai/talamus)](https://skills.sh/ampres-ai/talamus) ![license](https://img.shields.io/badge/license-Apache--2.0-blue) ![python](https://img.shields.io/badge/python-3.11%2B-blue)

**Your coding agent forgets why a decision was made as soon as the session ends.**

Talamus keeps the decisions, evidence, and corrections worth remembering as
ordinary Markdown, then gives Claude Code, Codex, Cursor, Gemini CLI, and any
MCP agent cited recall in the next session.

**No hosted account. No telemetry. No required embeddings. Plain search stays
on your machine; LLM-backed actions use only the engine you choose.**

Try the whole local retrieval loop first — no persistent install, account,
LLM, or hook, and no files written outside `./talamus-demo`:

```bash
uvx --from talamus talamus demo --root ./talamus-demo
uvx --from talamus talamus search "embedding" --root ./talamus-demo
uvx --from talamus talamus read "Embedding" --root ./talamus-demo
```

If local, inspectable agent memory is useful to you,
[star Talamus on GitHub](https://github.com/ampres-ai/talamus) — it helps other
builders discover a local-first alternative.

![Talamus demo — a completed agent session becomes cited, local memory for the next one.](https://raw.githubusercontent.com/ampres-ai/talamus/main/docs/assets/talamus-demo.gif)

Talamus is an open-source project by [Ampres](https://ampres.io), an independent AI and open-source lab.

## Connect an agent

Copy-pasteable arc, with the reproducible version in
[`scripts/demo/run_magic.py`](https://github.com/ampres-ai/talamus/blob/main/scripts/demo/run_magic.py):

1. Set up the project brain. `talamus setup` initializes the brain, chooses an engine, installs MCP for Claude Code, Cursor, Codex, OpenCode, and OpenClaw when detected, asks once before installing the session-capture hook, and can probe the engine with one tiny live call.

   ```bash
   talamus setup
   ```

2. Your agent session ends. The consented hook reads the transcript and git diff, applies the worth-remembering gate, writes only useful memory into this brain, and audits the event at `.talamus/logs/capture.log`.

3. A fresh session asks what happened and gets an answer from real notes, with sources.

   ```bash
   talamus recall "why did we choose FTS5?"
   talamus ask "why did we choose FTS5?"
   ```

4. Reproduce the scripted demo without spending LLM calls, or run it with your real engine.

   ```bash
   python scripts/demo/run_magic.py --fake
   python scripts/demo/run_magic.py --keep --engine claude-cli
   ```

## What is different

**TIME**: notes have version history, facts have valid-time windows, and `talamus ask --as-of 2026-01` answers from the brain as it was.

**MEANING**: the ontology is induced from evidence, versioned, promoted by measured rules, and used to cluster and route the brain.

**VERIFIABILITY**: every note carries provenance; `talamus verify` proposes corrections to review, and answers cite the notes they used.

## Measured comparison

The one-screen benchmark is rendered in the
[benchmark guide](https://ampres-ai.github.io/talamus/benchmarks/) and committed
as [`one-screen.md`](https://github.com/ampres-ai/talamus/blob/main/benchmarks/results/one-screen.md).
Every number below traces to a
[committed result artifact](https://github.com/ampres-ai/talamus/tree/main/benchmarks/results).

| corpus | metric | Talamus | BM25 | MiniLM vector DB |
|---|---:|---:|---:|---:|
| SciFact, English-only turf | recall@10 | **0.797** | 0.776 | 0.783 |
| SciFact, English-only turf | nDCG | **0.664** | 0.652 | 0.645 |
| Book, cross-language + vague | hit@10 | **0.971** | 0.829 | 0.743 |
| Book, cross-language + vague | recall@10 | **0.929** | 0.771 | 0.700 |

Also measured in committed artifacts: **−97.7% tokens** per answer versus loading the brain into context, refusal **1.000** on out-of-scope questions, and search latency p95 **72.6 ms** at 10k notes / p50 **624 ms** at 100k.

The honest part: retrieval quality tracks the LLM you bring. With a strong expansion engine, `talamus-smart` leads a strong multilingual dense model (`multilingual-e5`) on every metric including ranking (nDCG 0.847 vs 0.837); with a weak or free one, e5 leads ranking while Talamus keeps the best hit/recall — and on a slow local engine, plain `search` beats `--smart` outright. Every number traces to a committed artifact; the losses stay on the table.

## Engines

Bring the LLM you already have: `claude-cli`, `codex-cli`, `antigravity-cli` (agy), `opencode`, `ollama`, or `anthropic-api`.

## Quickstart

```bash
pipx install "talamus[mcp]"
talamus setup
talamus ingest ./notes && talamus ask "what should I remember?"
```

Run `talamus` for the status dashboard, `talamus quickstart` for essential commands, or `talamus ui` for the local React workbench.

Install the consent-aware Talamus agent skill from [skills.sh](https://skills.sh):

```bash
npx skills add ampres-ai/talamus --skill talamus-memory
```

OpenClaw can install the same standalone skill directly from ClawHub:

```bash
openclaw skills install @ampres-ai/talamus-memory
```

Installing the standalone skill does not install Talamus automatically. If the
CLI is missing, the skill explains the isolated installation choices and asks
before running one.

Gemini CLI can install Talamus directly from its extension gallery or from this
repository. The extension starts the pinned PyPI release through `uvx`, so it
does not modify the cloned source tree:

```bash
gemini extensions install https://github.com/ampres-ai/talamus --auto-update
```

goose can install the repository as an Open Plugin. This adds the consent-aware
memory skill and starts the pinned local MCP server for each new CLI session:

```bash
goose plugin install https://github.com/ampres-ai/talamus.git
```

The plugin requires `uv` on `PATH`; `uvx` downloads Talamus and its MCP
dependencies into an isolated cache on first use.

Containerized MCP (the brain remains in the mounted local folder):

```bash
docker run --rm -i -v "$PWD:/data" ghcr.io/ampres-ai/talamus:1.1.1
```

## Links

Docs: [quickstart](https://ampres-ai.github.io/talamus/quickstart/), [local-first agent memory](https://ampres-ai.github.io/talamus/local-first-agent-memory/), [agent install guide](https://github.com/ampres-ai/talamus/blob/main/llms-install.md), [commands](https://ampres-ai.github.io/talamus/commands/), [agent tool calling](https://ampres-ai.github.io/talamus/agent-tool-calling/), [configuration](https://ampres-ai.github.io/talamus/configuration/), [benchmarks](https://ampres-ai.github.io/talamus/benchmarks/), [architecture](https://ampres-ai.github.io/talamus/architecture/), [design principles](https://ampres-ai.github.io/talamus/design-principles/), [evaluation](https://ampres-ai.github.io/talamus/evaluation/), [multi-brain](https://ampres-ai.github.io/talamus/multi-brain/), [ontology](https://ampres-ai.github.io/talamus/ontology/).

Project: [security](https://github.com/ampres-ai/talamus/blob/main/SECURITY.md), [contributing](https://github.com/ampres-ai/talamus/blob/main/CONTRIBUTING.md), [roadmap](https://github.com/ampres-ai/talamus/blob/main/ROADMAP.md), [changelog](https://github.com/ampres-ai/talamus/blob/main/CHANGELOG.md).

Maintained by [Ampres](https://ampres.io). Source code and issue tracking live at [ampres-ai/talamus](https://github.com/ampres-ai/talamus).

## Development

```bash
pip install -e ".[dev,mcp]"
python dev.py
```

`python dev.py` runs ruff, format check, mypy, and unittest. Product behavior changes should update user docs in the same change.

## License

Apache-2.0.
