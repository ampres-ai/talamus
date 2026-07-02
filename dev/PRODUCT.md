# Talamus — the final product, defined

This is the hyper-detailed definition of what we are building and the bar that
"finished" must clear. It supersedes the historical PRD, vision and roadmap
documents (archived outside the repo). It changes only with the maintainer's
approval.

## The one-sentence product

**Talamus is a local-first knowledge compiler: it turns whatever you read,
write or work on into a navigable, cited, time-aware second brain that both
you and your AI agents share — powered entirely by the LLM you already have.**

## The thesis (why this is revolutionary)

Every competing memory system buys semantic power with infrastructure:
embedding models, vector databases, hosted graphs, pay-per-call APIs. Talamus
buys it with the **one intelligent resource the user already pays for** — a
coding-agent subscription (~€20/month: Claude, Codex or Gemini CLI) or a free
local model via ollama. Anyone, including non-technical users, gets:

- a **personal second brain**: real Markdown notes, browsable as a wiki
  (Obsidian-compatible), searchable in any language, with every claim traceable
  to its source;
- an **agent memory**: the same brain exposed to AI agents via MCP and CLI, so
  agents recall instead of re-reading, and remember what they learn across
  sessions.

Semantics is paid ONCE at ingest (the LLM writes canonical aliases, bilingual
retrieval text and symptom phrasings INTO the notes) and at ask time the LLM
translates the user's phrasing into corpus vocabulary. Zero marginal
infrastructure. Everything inspectable: the "semantic bridge" is readable text
in the note, not a vector — a human can see it and fix it.

## The three differentiators (the moat)

Versus the viral llm_wiki (10k+ stars), mem0, Zep/Graphiti and vector-DB RAG:

1. **TIME** — a bitemporal model. Notes have version history (transaction
   time) and facts have validity windows (valid time, append-only claims).
   Corrections invalidate, never delete. `ask --as-of` answers from the past.
2. **MEANING** — the emergent ontology. Relation types are not hand-defined:
   they are induced from evidence across the brain, named in canonical
   English, versioned, and promoted only by measured rules. The ontology
   clusters notes into domains, the domains into macro-areas: the brain
   builds its own table of contents, which routes every question.
3. **VERIFIABILITY** — active provenance. Every note knows its sources (file,
   locator, content hash). `verify` re-checks notes against sources and
   PROPOSES corrections to a review queue. Answers cite. The brain says "I
   don't know" rather than inventing.

None of the competitors has all three; none works without embeddings or
hosted services.

## Target users

1. **The knowledge worker / student** ("even the least technical"): owns PDFs,
   notes, articles. Wants: drop a 500-page book in, get a navigable wiki and
   honest cited answers, in their own language. Setup must take minutes
   (`talamus setup` detects engines and configures everything).
2. **The developer with AI agents**: wants agents that remember decisions,
   conventions and past sessions across projects. Uses MCP tools
   (search/recall/remember/neighbors/overview) and the session-capture hook.
3. **The team (future)**: shared brains; out of scope until after public
   launch.

## The complete experience (what "the product" includes)

- **Onboarding**: `talamus setup` → engine auto-detection (any of claude-cli /
  codex-cli / gemini-cli / ollama / API key), brain init + registration, MCP
  install, optional repo scan with dry-run consent. Under 10 minutes.
- **Ingest**: files (md/txt/pdf/docx/html), URLs, folders (incremental,
  hash-skipped), whole repositories (scan with secret redaction + code
  digests), agent sessions (capture hook with worth-remembering gate), single
  insights (`remember`). Big documents chunk deterministically and run as
  resumable jobs with cost estimates; engines are switchable mid-job.
- **Retrieval**: three-channel lexical+trigram index (no embeddings),
  cross-language by construction, milliseconds at 10k notes. `search`,
  `recall`, `neighbors`, `read`, `history`, `timeline`. Two tiers: plain
  `search` is instant and free (~0.86 hit, known-item lookup); `search
  --smart` adds cached LLM query expansion (Query2doc) for vague/paraphrased
  queries (~0.97 on a curated brain), still no embeddings and no per-query
  cost on repeats.
- **Ask**: hierarchical routing (macro-area → domain) + LLM query expansion +
  ranked selection + global escape seeds → budgeted context → cited answer in
  the question's language, honest refusal when the brain doesn't know.
  Federated: project brain + central brain in one query. `--as-of` for the
  past, `--trace` to see the route.
- **Curation**: review queue (corrections, stale sources, low-confidence
  notes), `verify` against sources, `consolidate` duplicates (propose →
  review → merge), `enrich` symptom vocabulary, ontology promotion flow.
- **Multi-brain**: Federated Hub with Project-Local Ownership — independent
  project brains + one central; central reads federate, writes stay local by
  default, `--all-brains` is explicit; promote notes project → central.
- **UI**: Flet workbench (desktop/web) — chat with as-of, search, notes,
  domains, physics graph (click node → open note), timeline, ingest with
  dry-run, review queue, ontology lab, full settings (engine, model, API keys,
  MCP). Dark, dense, 10k-stars-worthy.
- **For agents**: MCP server (read + write tools), token-cheap CLI commands,
  SDK (`recall.py`), session hook.

## The numeric bar for "finished" (v1.0 public)

| Metric | Bar | Status source |
|---|---|---|
| Ask hit-rate (right notes read), real corpus | ≥ 0.95 | STATE.md dashboard |
| `search` plain (instant, free) | ~0.86 lexical ceiling — acceptable for the fast tier | achieved |
| `search --smart` (Query2doc), curated enriched corpus | ≥ 0.92 | achieved (0.972 book) |
| Honest refusal on out-of-scope questions | answer-level guard, measured | achieved (RS8: refusal 1.000 cloud+local vs competitors ≤0.833; negatives set 8→30, 2026-07-02) |
| Search latency @ 10k notes | < 100 ms | achieved (p95 72.6 ms, re-measured 2026-07-02) |
| Routing token cost | ~log(N), measured | achieved (12× at 10k) |
| Scale | 100k notes usable | achieved (search p50 624 ms / p95 695 ms @ 100k, index 208 MB sqlite-fts5 — benchmarks/results/2026-07-02-scale-100k.json; growth is linear, a future optimization front) |
| Setup time, zero to first answer | < 10 min | achieved (re-verified live 2026-07-02: setup→scan→cited ask in ~3 min) |
| Works with a small local model (ollama) | full pipeline e2e | achieved (RS8: talamus-search correctness 0.800 fully local, gemma generator+judge, €0) |
| Multi-OS | Linux/macOS/Windows CI green | achieved |
| Quality floors in CI | recall/MRR/hit floors never regress | achieved |

Plus the non-numeric bar: every constraint in
[CONSTRAINTS.md](CONSTRAINTS.md) holds; docs (user + dev) match behavior; a
cold `pip install` works on a clean machine.

## Explicitly OUT of scope for v1.0

- Embeddings (optional extra, post-1.0 at the earliest, only with data).
- Team/multi-user sync, auth, hosted anything.
- Remote authenticated MCP endpoint for browser LLMs.
- Audio/video ingestion; OCR beyond the optional extra.
- Mobile UI.

## Competitive posture (keep honest)

Vector DBs reach ~98% semantic hit by paying query-time embedding
infrastructure. Our promise is different and is now demonstrated, not
promised: parity on the hard vague queries is reached via Query2doc (the
user's own LLM expands the query — `search --smart` hit 0.972, ask 0.972),
with ZERO embedding infra, plus time, meaning, verifiability and true local
ownership that they do not have. Where a gap remains (e.g. an un-enriched
mechanical brain, where smart search is ~0.78), we say so in STATE.md rather
than hand-waving.
