# Talamus

<!-- mcp-name: io.github.ampres-ai/talamus -->

[![CI](https://github.com/ampres-ai/talamus/actions/workflows/ci.yml/badge.svg)](https://github.com/ampres-ai/talamus/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/talamus)](https://pypi.org/project/talamus/) [![MCP Registry](https://img.shields.io/badge/MCP_Registry-active-5b5bd6)](https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.ampres-ai%2Ftalamus) [![Smithery](https://img.shields.io/badge/Smithery-install-111827)](https://smithery.ai/servers/ampres-ai/talamus) [![skills.sh](https://skills.sh/b/ampres-ai/talamus)](https://skills.sh/ampres-ai/talamus) ![license](https://img.shields.io/badge/license-Apache--2.0-blue) ![python](https://img.shields.io/badge/python-3.11%2B-blue)

**Your AI agent forgets why a decision was made as soon as the session ends.**

Talamus turns agent sessions, documents, notes, repos, and URLs into local,
source-grounded Markdown memory that the next session can search and cite.

**Markdown stays the source of truth. Search and graph stay on your machine. No
hosted account or required embeddings.**

Try the whole local retrieval loop first — no setup, account, LLM, or hook:

```bash
pipx install "talamus[mcp]"
talamus demo
talamus search "embedding"
talamus read "Embedding"
```

If local, inspectable agent memory should stay discoverable, click **Star** at
the top of this page. It is the clearest signal that Talamus is worth
maintaining in public.

![Talamus — Memory that survives the session.](docs/assets/talamus-social-preview.png)

Talamus is an open-source project by [Ampres](https://ampres.io), an independent AI and open-source lab.

## Connect an agent in 60 seconds

Copy-pasteable arc, with the reproducible version in [`scripts/demo/run_magic.py`](scripts/demo/run_magic.py):

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

The one-screen benchmark is rendered at [`docs/benchmarks.md`](docs/benchmarks.md) and committed at [`benchmarks/results/one-screen.md`](benchmarks/results/one-screen.md). Every number below traces to a committed artifact under [`benchmarks/results/`](benchmarks/results/).

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
docker run --rm -i -v "$PWD:/data" ghcr.io/ampres-ai/talamus:1.0.3
```

## Links

Docs: [quickstart](docs/quickstart.md), [local-first agent memory](docs/local-first-agent-memory.md), [agent install guide](llms-install.md), [commands](docs/commands.md), [agent tool calling](docs/agent-tool-calling.md), [configuration](docs/configuration.md), [benchmarks](docs/benchmarks.md), [architecture](docs/architecture.md), [design principles](docs/design-principles.md), [evaluation](docs/evaluation.md), [multi-brain](docs/multi-brain.md), [ontology](docs/ontology.md).

Project: [security](SECURITY.md), [contributing](CONTRIBUTING.md), [roadmap](ROADMAP.md), [changelog](CHANGELOG.md).

Maintained by [Ampres](https://ampres.io). Source code and issue tracking live at [ampres-ai/talamus](https://github.com/ampres-ai/talamus).

## Development

```bash
pip install -e ".[dev,mcp]"
python dev.py
```

`python dev.py` runs ruff, format check, mypy, and unittest. Product behavior changes should update user docs in the same change.

## License

Apache-2.0.
