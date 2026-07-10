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

## Retrieval quality

- **Session-capture quality benchmark** — a judged eval-set for how well
  captured agent sessions preserve the decision and the why, with a CI floor.
- **A third benchmark corpus** in a new domain, to guard against overfitting
  retrieval tuning to the existing corpora.
- **The embeddings decision, with data** — measure whether an *opt-in* local
  embedding channel adds anything the LLM-expansion route cannot; adopt only
  on a clear, reproducible win, and never as a requirement.

## Ingestion

- **Richer document extraction** — optional extras for docling and OCR;
  evaluate MarkItDown as an ingest front-end (would extend ingestion toward
  audio/video transcripts).
- **Ingest-quality benchmark** — measure how faithfully big-document chunking
  preserves boundary concepts, now that deterministic chunk overlap is in.

## Performance

- **Sub-100 ms plain search at 100k notes** — today's measured p50 at 100k is
  624 ms (usable, not magic). Profile and cut the dominant cost.
- **Cold-start and memory footprint** on a modest PC — measured and bounded.

## Workbench & UX

- **Command palette (Ctrl/⌘-K)** and full keyboard flow in the workbench.
- **Ontology insights surface** — show surprising links and gaps the inferred
  relation properties reveal (the inference layer already computes them).
- **Packaged desktop binary** (PyInstaller) so non-Python users can install.

## Agents

- **More engines** — kimi-cli when verifiable; Anthropic API
  thinking-budget passthrough.
- **Cross-brain ontology aggregation** — let the shared schema learn from
  every brain's evidence, not just each brain in isolation.

## Long term

- **Team / shared brains** — synchronization and multi-user review flows.
- **Remote, authenticated, read-only endpoint** for browser-based agents
  (deliberately out of scope until the security story is proven).
