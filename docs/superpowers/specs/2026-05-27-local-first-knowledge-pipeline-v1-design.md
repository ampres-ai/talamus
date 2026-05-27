# Local-First Knowledge Pipeline V1 Design

Date: 2026-05-27

## Status

Approved design direction for the next project phase.

This document supersedes the earlier Graphify-centered design. Graphify is no
longer part of the core architecture. The project will build its own
deterministic graph and retrieval layer from canonical notes, metadata,
wikilinks, and lexical search indexes.

## Purpose

Build a local-first knowledge pipeline that turns messy source material into a
source-grounded, graph-ready, Obsidian-compatible knowledge base for AI agents
and humans.

The first target user is a Forward Deployed AI Engineer or AI Engineer who needs
to ingest books, notes, PDFs, images, and work material into a reusable second
brain. The tool must also be designed as a future open source product:
beginner-friendly by default, powerful by configuration, and scalable enough to
support a future local UI that can eventually replace Obsidian.

## Product Positioning

The project is not a generic note-taking app.

It is a local-first knowledge compiler:

```text
messy source
-> validated Markdown source package
-> rich source-grounded canonical notes
-> Obsidian rendering
-> deterministic graph and lexical index
-> cited answers from real Markdown notes
```

The strongest product claim is token efficiency without losing source fidelity:
agents should not read an entire wiki or giant index. They should retrieve a
small candidate set through a graph plus lexical search, read the real notes,
optionally follow validated wikilinks, and answer with citations.

## Licensing Decision

Core license: Apache-2.0.

Rationale:

- Maximize adoption by individuals, consultants, and companies.
- Keep the core acceptable for enterprise use.
- Preserve future freedom to build a proprietary local UI or paid extensions.
- Avoid mandatory dependency on copyleft libraries.

Rules:

- The core must not require AGPL/GPL dependencies.
- Copyleft or commercial-license converters may exist only as optional adapters.
- Adapter license requirements must be documented clearly.
- Model weights are never bundled; users install and accept model licenses
  separately.

## Core Product Principles

1. Beginner-first UX.
2. Local-first by default.
3. Few V1 formats, robustly handled.
4. No hardcoded strategic choice: converters, OCR, LLMs, search, graph, and
   storage must be adapters behind stable interfaces.
5. Canonical data model first; Obsidian Markdown is a rendering target, not the
   primary data model.
6. Source provenance is mandatory for every important claim.
7. Wikilinks belong inside note bodies when they help reading and traversal.
8. Link generation is LLM-assisted but system-validated.
9. Deterministic graph construction replaces Graphify semantic extraction.
10. Lexical/BM25 search is a first-class retrieval layer, not a fallback hack.

## Beginner-First UX

The default path must work without adapter choices.

Target commands:

```powershell
brain init
brain ingest
brain ask "When should I use RAG instead of fine-tuning?"
brain status
brain doctor
brain review
```

Beginner mode requirements:

- Install and first run should be possible in minutes.
- Default configuration must be generated automatically.
- The user should not need to understand Docling, OCR, BM25, graph schemas, or
  storage adapters.
- Long-running tasks must show progress, elapsed time, current stage, current
  file, and an estimate when possible.
- Long-running tasks must be safely resumable.
- Failures must route to review or failed folders with clear explanations.
- Advanced adapter configuration must be opt-in.

Power-user configuration exists, but is hidden from the basic flow:

```yaml
storage:
  provider: obsidian
conversion:
  pdf: docling
ocr:
  provider: ollama
  model: glm-ocr
llm:
  provider: claude-cli
search:
  provider: builtin-bm25
graph:
  provider: deterministic-json
```

## V1 Format Scope

V1 prioritizes fewer formats with robust validation.

V1 target formats:

- PDF
- images and screenshots
- Markdown, TXT, and personal notes
- DOCX if validation shows the adapter is reliable enough without harming the
  beginner flow

Explicit V2 or later:

- YouTube and online video
- raw audio transcription
- web crawling
- dynamic websites
- PPTX/XLSX
- ZIP archives
- batch crawling or connector ecosystems

The architecture must still support these later through adapters.

## Source Storage Layers

The workspace keeps three canonical storage layers:

```text
AI Space/raw/
  Preserved originals.

AI Space/normalized/
  Source-faithful Markdown packages.

FDE Brain/
  Obsidian-rendered final notes.
```

Derived layers:

```text
AI Space/index/
  Lexical/BM25 and optional hybrid search indexes.

AI Space/graph/
  Deterministic graph outputs built from canonical notes.

AI Space/logs/
  Run, decision, validation, migration, and promotion logs.

AI Space/review/
  Items needing human review.

AI Space/failed/
  Technical failures.
```

Graph and index files are derived and must be rebuildable.

## Normalized Source Package

Every processed source becomes a normalized package:

```text
AI Space/normalized/<source_type>/<source_slug>/
  manifest.json
  sections/
    001-title.md
    002-title.md
  assets/
  quality-report.json
```

Each section must include provenance metadata:

- raw path
- raw hash
- source type
- source id
- section id
- title
- page, locator, or range
- converter used
- OCR used or not
- confidence
- previous section
- next section
- warnings

Normalized Markdown is source-faithful. It should not try to be beautiful
Obsidian writing.

## Conversion Layer

The conversion layer is adapter-based.

V1 default strategy:

- PDF quality converter: Docling.
- OCR adapter: Ollama with glm-ocr by default.
- Image/screenshot conversion: OCR/VLM adapter with confidence reporting.
- Markdown/TXT: passthrough plus classification and provenance.
- DOCX: adapter candidate through a permissive tool such as MarkItDown or
  Pandoc, gated by validation.

Important adapter decisions:

- Docling is the V1 default for quality PDF conversion because it is permissive
  and quality-oriented, but it must not be hardcoded as the only PDF path.
- PyMuPDF4LLM can be supported later as an optional fast PDF adapter, but its
  AGPL/commercial licensing means it cannot be a mandatory Apache-2.0 core
  dependency.
- Marker can be supported later as an optional adapter, but its license must be
  documented clearly.
- Claude, Codex, Ollama, or other local/remote models can be OCR/VLM adapters,
  but users must opt into their installation and cost/usage limits.

## Conversion Quality Gate

The system should not claim perfect conversion. It should implement best-effort
conversion with explicit quality gates.

Quality checks:

- extracted text amount
- empty pages or empty sections
- OCR confidence
- missing page locators
- suspicious encoding artifacts
- repeated headers and footers
- section length outliers
- table loss warnings
- image or figure loss warnings
- low-confidence layout extraction
- detected table of contents, index, copyright, and cover sections

Low-quality items route to:

```text
AI Space/review/low-confidence-normalization/
AI Space/review/needs-human/
AI Space/failed/technical-failures/
```

The system should preserve raw and normalized material even when a section is not
distilled into final notes.

## Hardware And Performance Requirements

Docling and OCR can be computationally heavy. V1 must include infrastructure for
transparent performance rather than hiding long tasks.

Minimum target:

- modern CPU
- 8 GB RAM
- SSD preferred
- small to medium documents

Recommended:

- 16 GB RAM
- GPU acceleration when available
- enough disk space for raw, normalized, cache, and assets

Required product behavior:

- `brain doctor` checks available tools, models, memory hints, and GPU/Ollama
  availability where possible.
- Large sources get a size/time warning before deep conversion.
- Jobs persist progress.
- Jobs can resume safely after interruption.
- Caches prevent repeated conversion of unchanged sources.
- No command may run silently for hours without stage/progress output.

The system should not promise that every 300-page PDF can finish in one hour.
Instead, it should provide progressive output, resumability, and clear estimates.

## Semantic Note Extraction

The extraction layer converts normalized sections into canonical note objects.

The LLM should not be the final Markdown writer. It should produce structured
candidate note objects that are validated, deduplicated, linked, and rendered by
the system.

Canonical note object fields:

```json
{
  "id": "stable-id",
  "title": "Retrieval-Augmented Generation",
  "aliases": ["RAG", "retrieval augmented generation"],
  "folder": "AI Engineering/Retrieval",
  "tags": ["ai-engineering", "retrieval", "rag"],
  "summary": "Human-facing summary.",
  "retrieval_text": "Search-optimized terms and explanations.",
  "body_sections": {
    "core_idea": "...",
    "practical_use": "...",
    "examples": "...",
    "failure_modes": "...",
    "implementation_notes": "..."
  },
  "proposed_links": [
    {
      "anchor": "vector store",
      "target": "Vector Store",
      "reason": "Needed to understand retrieval infrastructure."
    }
  ],
  "relations": [
    {
      "source": "Retrieval-Augmented Generation",
      "relation": "uses",
      "target": "Vector Store",
      "confidence": 0.85
    }
  ],
  "sources": [
    {
      "raw_path": "AI Space/raw/pdf/example.pdf",
      "normalized_path": "AI Space/normalized/pdf/example/sections/004-rag.md",
      "locator": "pages 42-48",
      "source_hash": "sha256:...",
      "supported_claims": ["..."]
    }
  ],
  "confidence": 0.86
}
```

Note quality requirements:

- Notes must be focused, but not overly synthetic.
- Notes should emulate useful human knowledge: rich, connected, articulated,
  and actionable.
- Notes must include enough context to be useful when read alone.
- Notes must not become source dumps.
- Notes must include provenance for important claims.
- Notes must include retrieval text for search and graph navigation.

## Batch Link Resolution

Wikilinks must work even when two linked notes are created in the same ingestion
batch.

Pipeline:

```text
1. Generate candidate note objects for the batch.
2. Build a temporary note registry:
   - existing vault notes
   - existing aliases
   - candidate batch notes
   - candidate batch aliases
3. Resolve proposed links against the combined registry.
4. Render valid links into note bodies.
5. Route unresolved but important concepts to review or future-note candidates.
6. Validate no broken wikilinks before committing.
```

Example:

If the batch creates `Retrieval-Augmented Generation` with alias `RAG`, another
note in the same batch can safely render:

```markdown
Un modo tipico e usare [[Retrieval-Augmented Generation|RAG]] per collegare il
modello a fonti esterne.
```

Rules:

- Body wikilinks are encouraged when they improve reading and exploration.
- Weak links can remain in `Related` or graph metadata.
- Broken links must not be rendered into final notes.
- Important missing concepts should be logged for review.

## Obsidian Storage Adapter

Obsidian is the first storage adapter, not the permanent product boundary.

The canonical note object renders to Obsidian Markdown:

- YAML frontmatter / Properties
- aliases
- tags
- wikilinks
- sources
- summary
- body sections
- related links

The future local UI should be able to read the same canonical data and render
its own interface without requiring Obsidian.

## Deterministic Graph Layer

Graphify is excluded from the core.

The graph is built deterministically from canonical notes and rendered Obsidian
notes.

Graph nodes:

- notes
- aliases
- concepts
- tags
- sources
- source sections
- folders/domains

Graph edges:

- wikilinks
- aliases
- explicit relations
- shared source
- source supports note
- tag membership
- folder membership
- backlinks

Graph node attributes:

- label
- aliases
- path
- folder
- tags
- summary
- retrieval_text
- source locators
- confidence
- updated timestamp

The graph must be lightweight. It is an index and routing layer, not the source
of truth.

## Lexical And Hybrid Retrieval

Retrieval must combine deterministic graph traversal with lexical search.

V1 should include or implement a local BM25-style index over:

- note titles
- aliases
- tags
- body text
- retrieval_text
- source claims
- normalized source titles and headings

QMD is an interesting candidate adapter because it is local, agent-oriented, and
supports BM25, vector, and hybrid search. It should be evaluated, but not made a
mandatory core dependency until maturity and operational fit are proven.

Fallback candidates:

- built-in BM25 implementation
- SQLite FTS5
- Tantivy-based adapter
- Qdrant or another external engine as an advanced adapter

Default retrieval flow:

```text
1. Run lexical search over note retrieval text and aliases.
2. Use the graph to expand to close neighbors.
3. Read the real Markdown notes.
4. Optionally follow validated wikilinks at depth 1 or 2.
5. Answer with citations from notes and their precompiled sources.
```

## Ask Layer

The ask tool must never answer from graph metadata alone.

It should:

- retrieve candidate notes through search and graph
- read real Markdown notes
- optionally expand through body wikilinks
- include citations
- report which model answered
- support read-only mode
- avoid automatic promotion when file changes are forbidden

If retrieval falls back to normalized sources, stable reusable knowledge should
be promoted into final notes when file changes are allowed.

## Update Infrastructure

Because the project will evolve through many small improvements, update
infrastructure is part of the product design.

CLI update principles:

- install through a standard Python CLI distribution path such as `pipx`
- provide `brain doctor` to detect outdated versions
- provide `brain update` or clear instructions for updating
- never silently auto-update core code during a knowledge run
- run migrations explicitly and log them
- keep rollback possible through git and backups

Future local UI:

- may check for updates automatically
- must ask before applying updates
- must support rollback or safe recovery

## Configuration

V1 should generate a default config at initialization.

Basic users should not edit it.

Advanced users can override:

- storage adapter
- converter adapter
- OCR adapter
- LLM adapter
- search adapter
- graph adapter
- cache directory
- review policies
- note templates

Config must be versioned and migratable.

## Logging And Audit

Every meaningful run should produce logs:

```text
AI Space/logs/runs/
AI Space/logs/decisions/
AI Space/logs/errors/
AI Space/logs/migrations/
AI Space/logs/retrieval/
```

Logs should include:

- run id
- source files
- raw archive paths
- normalized output paths
- converter and OCR adapter used
- model adapter used
- notes created or updated
- links resolved
- links rejected
- graph/index rebuilt
- review items created
- elapsed time per stage
- errors and retries

## Git And Safety

Git remains the safety layer.

Rules:

- never permanently delete raw originals
- checkpoint before destructive rebuilds
- keep unrelated local UI state out of commits
- commit successful ingestion/rebuild outputs intentionally
- do not clean `pending` until raw archive and logs are written
- preserve recovery paths for interrupted runs

## V1 Success Criteria

V1 succeeds when a beginner can:

```powershell
brain init
brain ingest
brain ask "..."
```

and get:

- raw originals preserved
- normalized Markdown packages created
- quality reports written
- rich Obsidian notes generated
- body wikilinks rendered and validated
- deterministic graph built
- lexical search index built
- cited answers from real Markdown notes
- clear progress and recovery on long jobs

Acceptance checks:

- no broken wikilinks in final notes
- every final note has aliases, tags, provenance, and retrieval text
- every important claim has a source locator
- graph and search index are rebuildable
- `pending` is empty only after safe processing
- interrupted jobs can resume or fail cleanly
- beginner commands do not require adapter knowledge

## Non-Goals For V1

- SaaS or multi-tenant hosted product
- proprietary UI
- Graphify integration
- broad connector ecosystem
- video/audio ingestion
- web crawling
- guaranteed perfect conversion
- guaranteed one-hour processing for every 300-page book
- automatic silent updates

## Risks And Mitigations

### Risk 1: Graph Plus BM25 Misses The Right Notes

Mitigation:

- retrieval_text is mandatory
- aliases and related terms are generated and validated
- BM25 is first-class
- graph expansion follows validated relations and body wikilinks
- optional hybrid/vector adapters can be added later

### Risk 2: Docling Is Too Slow For Local Beginner UX

Mitigation:

- show progress and ETA
- cache conversions
- support resume
- add fast converter adapter later
- warn on large files
- keep PDF converter configurable

### Risk 3: LLMs Generate Bad Links Or Bad Notes

Mitigation:

- use canonical note objects, not freeform final Markdown
- validate links against existing vault plus same-batch candidates
- reject broken links
- validate provenance
- route ambiguous/missing concepts to review
- keep deterministic rendering

### Risk 4: Too Many Adapters Confuse Users

Mitigation:

- beginner mode hides adapter choices
- defaults work out of the box
- advanced config is opt-in
- docs separate quickstart from advanced customization

### Risk 5: Future UI Replacement Becomes Hard

Mitigation:

- canonical note objects are the primary data model
- Obsidian is only the first storage adapter
- graph and search use canonical metadata, not Obsidian-only behavior

## Documentation Requirements

The project must be easy to adopt.

Required docs:

- 5-minute quickstart
- beginner workflow
- supported sources
- hardware expectations
- troubleshooting
- model setup
- adapter configuration
- Obsidian adapter behavior
- privacy/local-first explanation
- licensing and optional adapter license notes

## Next Phase

After this design is accepted, create an implementation plan that:

1. Removes Graphify from the core path.
2. Introduces canonical source and note models.
3. Reworks conversion around validated normalized packages.
4. Adds or evaluates Docling as the V1 PDF quality converter.
5. Builds deterministic graph generation.
6. Adds lexical/BM25 search.
7. Updates ask retrieval to use search plus graph plus real Markdown notes.
8. Adds beginner CLI commands and progress/resume infrastructure.
9. Updates docs and protocol files.

