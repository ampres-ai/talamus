# Talamus

[![CI](https://github.com/GCrapuzzi/Talamus-Wiki/actions/workflows/ci.yml/badge.svg)](https://github.com/GCrapuzzi/Talamus-Wiki/actions/workflows/ci.yml) ![license](https://img.shields.io/badge/license-Apache--2.0-blue) ![python](https://img.shields.io/badge/python-3.11%2B-blue)

**Local-first memory with time, meaning, and verifiability — for your second brain and your AI agents.**

Talamus compiles your sources (documents, notes, and agent work sessions) into
**source-grounded, cross-linked concept notes**, builds a typed **graph as an
index**, and answers questions **with citations** — all on your machine, on the
LLM engine you already use.

<!-- demo GIF goes here: talamus demo → search → read -->

> Markdown notes you can edit in Obsidian · a graph that routes retrieval ·
> provenance on every claim · usable from the CLI, the SDK, and MCP.

## Why Talamus

Most "AI memory" is either a pile of vector chunks (no structure, no provenance)
or a cloud service (your knowledge leaves your machine). Talamus is built on three
properties that, **together**, nothing else gives you:

- **TIME** — a bitemporal model: contradictions *invalidate* old facts instead of
  deleting them — `talamus timeline`, `ask --as-of 2026-01`. *(shipped: transaction
  history + valid-time claim overlay)*
- **MEANING** — a typed, **self-emerging ontology**: free-form relation surfaces
  the fixed types can't explain are induced into *candidate types*, reviewed,
  promoted, versioned — and measurably improve retrieval (`talamus ontology`).
  *(shipped: fixed types + Ontology Lab; experimental: emergent schema at scale)*
- **VERIFIABILITY** — every note keeps its **sources**; verify single notes or in
  batch, with proposed corrections going through a review queue (`talamus verify
  --all`). *(shipped)*

Plus a wedge the others don't optimize for: **memory for agents** that need
current, cited, reasoned truth.

## Talamus vs the alternatives

|                                   | Plain RAG | llm_wiki            | Zep / mem0 | **Talamus**       |
| --------------------------------- | --------- | ------------------- | ---------- | ----------------- |
| Local-first                       | varies    | ✅                  | ❌ cloud   | ✅                |
| Human-editable notes (Obsidian)   | ❌        | ✅                  | ❌         | ✅                |
| Typed ontology for reasoning      | ❌        | ❌ statistical graph | partial    | ✅                |
| Keeps history / "truth at time T" | ❌        | ❌ overwrites        | partial    | ✅ *(MVP)*        |
| Provenance + correct-from-source  | ❌        | tracking only       | partial    | ✅                |
| Agent memory (read + write, MCP)  | ❌        | partial             | ✅         | ✅                |

## Quickstart

```bash
pipx install talamus            # or: pip install talamus

talamus demo                    # try a small example brain instantly (no LLM)
talamus search "embedding"

talamus init                    # your own brain (auto-detects your LLM engine)
talamus ingest report.pdf       # PDF / DOCX / HTML / Markdown / URL -> linked concept-notes
talamus import-vault ~/vault    # coming from Obsidian/Notion? 1:1 import, zero LLM cost
talamus ask "how does X work?"  # cited answer
talamus ui                      # optional web workbench (pip install talamus[ui])
```

Run `talamus` with no arguments for a status panel, or follow the
**[10-minute quickstart](docs/quickstart.md)**.

## Choose your engine

Talamus runs on what you already have — set it in `talamus.json` or `TALAMUS_LLM_PROVIDER`:

- `claude-cli` — your Claude subscription (default if `claude` is on PATH)
- `codex-cli` — your ChatGPT subscription (Codex is bundled with it)
- `gemini-cli` — your Gemini subscription
- `opencode` — opencode, with whatever providers you configured in it
- `antigravity-cli` — Google Antigravity (`agy`)
- `ollama` — a local model, fully offline (`TALAMUS_LLM_MODEL=llama3`)
- `anthropic-api` — the Anthropic API (`ANTHROPIC_API_KEY`)

Every engine gets per-task **model+effort tiering** automatically: bulk work
(extraction, routing) runs on the cheap tier, the answer you read on the strong
one — top quality while burning as little of your subscription as possible.

## For agents (MCP)

```bash
talamus mcp install             # writes .mcp.json for Claude Code / Cursor / Desktop
talamus hook                    # prints a SessionEnd hook to auto-capture your work
```

Agents `search` / `read_note` / `recall` / `overview` / `neighbors` to read the brain,
and `remember` to grow it. The graph is an **index, not the answer** — agents read the
real notes and cite them.

## Browse it like a wiki

Open `notes/` as an Obsidian vault: notes cross-link with `[[wikilinks]]`, so you
navigate the knowledge by hovering and clicking. Prefer a dedicated app?
**`talamus ui`** — the local web workbench (`pip install talamus[ui]`) — gives you
chat, search, clickable wikilinks, graph navigation, and domain browsing.

## How it works

Sources (Markdown, text, **PDF, DOCX, HTML, URLs**) are normalized and preserved; an
LLM extracts atomic **concept notes** (with sources, typed relations, and wikilinks);
Talamus builds rebuildable indexes (graph + BM25 + ontology) and a hierarchical
**domain overview**. Retrieval routes through the overview, then **reranks** a union of
graph + BM25 candidates, and fits the context to a **token budget** so answer cost stays
flat as the brain grows. Answers cite the notes they used, and `talamus eval` measures
retrieval quality (recall@k / MRR) so changes are judged by numbers, not vibes.

Storage is **hybrid**: `notes/*.md` is the human-editable view (Obsidian-compatible),
`.talamus/cache/` holds the machine truth (provenance) and the derived indexes;
`talamus reindex` folds your hand-edits back in. The core is **Python stdlib-only**;
extras (MCP, engines) are optional. See **[architecture](docs/architecture.md)**.

## How it compares (measured)

A real head-to-head against a MiniLM dense vector-DB RAG pipeline
(sentence-transformers + FAISS) and vanilla BM25, same corpus/queries/judgments
([details](dev/research/2026-06-rs5-competitive-shootout.md)):

| corpus | metric | Talamus | BM25 | Vector DB |
|---|---|---|---|---|
| BEIR SciFact (English, dense's turf) | recall@10 | 0.776 | 0.776 | 0.783 |
| BEIR SciFact | hit@10 | 0.793 | 0.797 | 0.793 |
| Cross-language + vague (our turf) | recall@10 | **0.886** | 0.771 | 0.700 |
| Cross-language + vague | hit@10 | **0.971** | 0.829 | 0.743 |

**On the vector DB's home turf we tie MiniLM — with zero embedding
infrastructure. On cross-language and vague queries we beat that MiniLM
baseline.** A stronger multilingual dense model changes the honest story: on
the book corpus multilingual-e5 leads nDCG **0.837** / MRR **0.857**, while
`talamus-smart` keeps the best hit **0.971** / recall **0.886**. The edge is not
"always beats dense"; it is zero embedding infra plus time, meaning and
verifiability (100% of notes source-resolvable; 97.7% fewer tokens than loading
the brain).

## Use cases

- **Second brain** — compile your reading and notes into a connected, cited wiki.
- **Agent memory** — give your agents a local, structured, verifiable memory they
  can both read and grow.

## Status & roadmap

**Shipped** (tested, gate-green): the sources → notes → cited-answers loop;
**per-task engine tiering** (each operation picks the cheapest model that's good
enough); **multi-brain** with a federated read index (`brains`, `--all-brains`)
and a **shared emergent ontology** across brains; **repo scan** with dry-run,
secret redaction and resumable jobs (`scan`, `jobs`); **persistent indexes**
(sqlite/FTS5 — search p95 at 10.000 notes: **72 ms**, usable at 100k); the
**Ontology Lab** (emergent relation types: induce → review → promote, with
measured retrieval lift); the **temporal model** (`timeline`, `ask --as-of`);
**batch verification** with a review queue; multi-format ingestion
(PDF/DOCX/HTML/URL) and **Obsidian/Notion vault import** (`import-vault`, no LLM);
the CLI dashboard; the **MCP server** (read + write tools, including cited `ask`,
`verify`, and `read_note` as-of); the **React web workbench** (`talamus ui`) with
the time-travel and verify moats visible in the note inspector.

**Experimental**: emergent-schema quality at large scale (metrics built-in:
`ontology eval`/`stability`); UI runtime polish.

**Roadmap** ([details](dev/ROADMAP.md)): security hardening + public launch;
frictionless MCP install across agents; absurd-performance pass; then OCR & more
formats, optional local embeddings (measured), packaged installers.

## Development

```bash
pip install -e ".[dev,mcp]"
python dev.py                    # lint + types + tests
```

## License

Apache-2.0.
