# Roadmap

Where Talamus is going. Order reflects priority; everything here is subject to
the [design principles](docs/design-principles.md) — in particular, nothing
ships without measurements, and the free/local core is never weakened.

## Near term

- **v1.0 on PyPI** — the package is release-ready; publishing is the
  maintainer's click.
- **Recorded 60-second demo** — the end-to-end "your agent remembers" arc
  (`scripts/demo/run_magic.py`) captured as a short video for the README.
- **Security debt** — close the four known non-blocking items tracked in
  [SECURITY.md](SECURITY.md): owner-only credentials file, MCP read-only by
  default with `--enable-writes`, secret detection over PDF/DOCX text,
  YAML-safe frontmatter.

## Freshness by default (the temporal guarantee)

Today `--as-of` answers from the past on request; the complement is a
guarantee that the *default* answer is never stale, even when old and new
versions of a fact entered as different notes:

- **Dated context** — every note placed in an answer's context carries its
  timestamp, and the answer contract prefers the most recent when notes
  conflict — saying explicitly that the information changed.
- **Claims-aware answers** — the valid-time claim store (already recorded,
  already invalidate-not-delete) feeds the answer: "X was valid until March;
  superseded by Y".
- **Supersedes detection at ingest** — when a new note conflicts with an
  existing one on the same subject, Talamus proposes the `supersedes`
  relation and the claim closure automatically (review-gated), so the
  temporal graph populates itself.
- **A temporal benchmark** proving it: procedure v1 (2025) + v2 (2026) in the
  brain, question asked "today" must answer v2 and note the change.

## The Curator (autonomous brain maintenance)

Large brains cannot depend on the owner clicking through every review. The
direction: an agent that maintains every registered brain by itself, with a
safety split:

- **Safe fixes are applied automatically** — mechanical corrections (a source
  file moved but its content re-verified identical, duplicate groups with
  perfect overlap, stale derived caches). Every automatic action is audited
  and reversible: the append-only history makes undo a guarantee, not a hope.
- **Judgment calls are prepared, not taken** — content corrections, merges
  that change prose, promotions to the central brain arrive as ready-to-apply
  proposals with a one-click accept, and the user is notified.
- **Brain health runs** — a schedulable pass over all registered brains
  (provenance checks, duplicate scan, ontology candidates, pending captures)
  ending in one readable report instead of N manual commands.
- **Promotion scouting** — session captures classify what they learn as
  project-specific or general; general knowledge produces a promotion
  proposal to the central brain.

## Ingestion

- **Watch mode (auto-ingest)** — drop a file into a watched project folder
  and it becomes notes without a manual command, llm-wiki-style. Consent
  moves from per-run to per-folder: enabling the watch is the consent, with a
  per-day cost cap and everything logged.
- **Richer document extraction** — optional extras for docling and OCR;
  evaluate MarkItDown as an ingest front-end (toward audio/video
  transcripts).
- **Ingest-quality benchmark** — measure how faithfully big-document chunking
  preserves boundary concepts.

## Engines & resilience

- **Fallback chain** — an ordered list of engines per brain: when one hits
  its usage limit mid-operation, the next takes over (a local ollama model as
  the last resort means captures and answers never fully stop). Shipped
  already: limit detection with actionable errors, resumable job pause, and
  parked-capture retry (`talamus hook --retry`).
- **Workbench surfacing** — pending captures, limit warnings and the retry
  action visible on Home, not only in `doctor`.
- **More engines** — kimi-cli when verifiable; Anthropic API thinking-budget
  passthrough. The deprecated gemini-cli adapter is removed after a
  transition release.

## Retrieval quality

- **Unicode-aware indexing** — tokenization and n-grams for non-Latin
  scripts (Chinese, Japanese, Russian, Arabic), so plain `search` works
  everywhere `ask` already does; pluggable per-language stemming.
- **Session-capture quality benchmark** — a judged eval-set for how well
  captured sessions preserve the decision and the why, with a CI floor.
- **A third benchmark corpus** in a new domain, to guard against overfitting.
- **The embeddings decision, with data** — measure whether an *opt-in* local
  embedding channel adds anything the LLM-expansion route cannot; adopt only
  on a clear, reproducible win, never as a requirement.

## Workbench & UX

- **A search bar** — instant-as-you-type plain search everywhere, with an
  "expand with AI" toggle (smart search); today the workbench only has Ask.
- **Plain-language brain flags** — "federated"/"sensitive" become
  human-readable toggles ("shared in global searches" / "private"),
  switchable from the Brains view, not only from the CLI.
- **Command palette (Ctrl/⌘-K)** and full keyboard flow.
- **Ontology insights surface** — show surprising links and gaps the inferred
  relation properties reveal (the inference layer already computes them).
- **Packaged desktop binary** (PyInstaller) so non-Python users can install.

## Agents

- **Interactive `mcp install`** — a checkbox menu of detected agents instead
  of flags, and **opencode as a fourth install target** (it consumes MCP; the
  menu explains its two roles: engine vs agent).
- **Cross-brain ontology aggregation** — let the shared schema learn from
  every brain's evidence, not just each brain in isolation.

## Performance

- **Sub-100 ms plain search at 100k notes** — today's measured p50 at 100k is
  624 ms (usable, not magic). Profile and cut the dominant cost.
- **Cold-start and memory footprint** on a modest PC — measured and bounded.

## Long term

- **Team / shared brains** — synchronization and multi-user review flows.
- **Remote, authenticated, read-only endpoint** for browser-based agents
  (deliberately out of scope until the security story is proven).
