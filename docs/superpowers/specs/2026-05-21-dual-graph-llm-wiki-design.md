# Dual Graph LLM Wiki Design

Date: 2026-05-21

## Purpose

This workspace will become a work second brain for a Forward Deployed AI Engineer.

The system is a local-first LLM Wiki inspired by Karpathy's raw-sources-to-maintained-wiki pattern. It separates raw capture, normalized source material, compiled Obsidian knowledge, retrieval graphs, logs, and agent protocols.

The core goal is to let the knowledge base grow without forcing an AI agent to read the whole vault or a giant index. Graphify is used as a derived routing layer, while Markdown files remain the source of truth.

## Primary Roles

- `FDE Brain` is the final Obsidian vault.
- `AI Space` is the AI operating area.
- Claude Code is the primary scheduled pipeline runner.
- Codex is the manual development and maintenance agent.
- Both Claude Code and Codex can answer questions against the knowledge base.

## Non-Goals

- Do not impose a rigid domain taxonomy at the start.
- Do not create one final note per source.
- Do not use Graphify as the source of truth.
- Do not write Graphify's generated Obsidian export into `FDE Brain`.
- Do not require external API keys for the first version.
- Do not make `AI Space/normalized` Obsidian-native; it only needs to be AI-readable and source-faithful.

## Workspace Layers

```text
AI Space/pending/
  Temporary unstructured drop zone. The user can put any files or notes here.

AI Space/raw/
  Archive of processed originals.

AI Space/normalized/
  Source-faithful Markdown or AI-readable output produced by parsers and OCR.

AI Space/graph/brain/
  Graphify output derived from FDE Brain.

AI Space/graph/sources/
  Graphify output derived from AI Space/normalized.

AI Space/logs/
  Run logs, decision logs, error logs, and promotion logs.

AI Space/review/
  Ambiguous items, conflicts, low-confidence OCR, and cases needing human judgment.

AI Space/failed/
  Technical failures.

AI Space/system/
  Shared agent protocol used by Claude Code and Codex.

FDE Brain/
  Final Obsidian vault containing only compiled knowledge.
```

## Canonical And Derived Data

Canonical layers:

- `AI Space/raw`
- `AI Space/normalized`
- `FDE Brain`
- `AI Space/logs`
- `AI Space/system`

Derived layers:

- `AI Space/graph/brain`
- `AI Space/graph/sources`

Graph output is always regenerable and must not contain unique knowledge that is absent from canonical files.

## Core Principles

1. Structure emerges from sources and usage.
2. `FDE Brain` is compiled knowledge, not a source archive.
3. Reusable patterns are first-class outputs from the start.
4. A source may update several notes, create one note, or create no final note.
5. Every important claim in `FDE Brain` must carry provenance inside the note.
6. Every answer from the knowledge base must cite sources.
7. Graphify routes the agent to relevant files; the agent must still read the real Markdown files.
8. Query-time use of `AI Space/normalized` triggers same-turn promotion into `FDE Brain`.
9. Git is the safety and audit layer.

## Local Engines

Required or preferred local engines:

- Scheduled agent: Claude Code.
- Manual/development agent: Codex.
- OCR: GLM-OCR locally through Ollama.
- Retrieval graph: Graphify.
- Graphify backend preference: `claude`.

External API keys are optional fallbacks and are not required for V1.

The pipeline must check availability of required local components before it performs destructive cleanup of `pending`.

## Obsidian Markdown Guidance

`FDE Brain` authoring should use the Obsidian Markdown skill as an implementation reference:

```text
kepano/obsidian-skills@obsidian-markdown
```

This skill is not a runtime dependency of the wiki. It is a writing and editing guide for agents that modify `FDE Brain`, especially for:

- Obsidian Properties/frontmatter
- wikilinks
- aliases
- tags
- links to headings
- callouts where appropriate
- embeds only when useful
- Obsidian-compatible Markdown conventions

Claude Code and Codex should follow this guidance whenever they create or edit final notes in `FDE Brain`.

## Ingestion Pipeline

Scheduled ingestion runs over the whole `AI Space/pending` folder. `pending` is intentionally unstructured and should be empty after a successful run.

Pipeline:

```text
1. Snapshot
2. Classify
3. Archive
4. Normalize
5. Segment
6. Register
7. Distill
8. Integrate
9. Graph Update
10. Log
11. Commit
12. Clean Pending
```

### Snapshot

Record the files present in `pending`: paths, sizes, timestamps, hashes, and batch ID.

### Classify

Classify inputs without requiring user-provided structure. Expected categories include:

- personal note
- book
- article
- PDF
- EPUB
- screenshot or image
- code or project artifact
- web clipping
- prompt or template
- idea
- course material
- unknown

### Archive

Move originals from `pending` into `AI Space/raw`, using stable names that avoid collisions.

No source original should be permanently deleted by the pipeline.

### Normalize

Create AI-readable source material in `AI Space/normalized`.

Expected behavior:

- EPUB and digital text use local extraction when possible.
- Digital PDFs use local parsing when possible.
- Scanned PDFs and complex images use GLM-OCR through Ollama.
- Low-confidence OCR goes to review.
- Large files are segmented before later agent use.

### Segment

Long sources are split into useful source units such as chapters, sections, or pages.

Normalized Markdown should preserve source fidelity over beauty. It does not need Obsidian wikilinks, tags, or final-note structure.

### Register

Register the connection between original files and normalized outputs so future provenance can be built without reverse-engineering.

### Distill

Extract stable concepts, reusable patterns, checklists, playbooks, decision frameworks, examples, anti-patterns, tools, and case-study material.

Every ingestion must ask: "Does this source contain a reusable pattern?"

### Integrate

Modify `FDE Brain` directly when the source contains stable or reusable knowledge.

Allowed actions:

- update an existing note
- create a new note
- update source metadata in a note
- update Obsidian links between notes
- leave the source only in `raw` and `normalized` if it is not ready for final compilation
- move ambiguous material to review

### Graph Update

Update both graphs after ingestion:

- Source Graph from `AI Space/normalized`
- Brain Graph from `FDE Brain`

If a graph cannot be updated, mark it stale and log the reason.

### Log

Write run, decision, error, and promotion logs.

### Commit

Commit the completed run atomically with git.

### Clean Pending

Empty `pending` only after inputs are safely archived or moved to review/failed.

## Fault Tolerance

The pipeline continues processing the rest of a batch when one item fails.

```text
ambiguous item -> AI Space/review/
technical failure -> AI Space/failed/
successful item -> raw + normalized + optional FDE Brain integration
```

If the run fails before safe archiving, do not clean `pending`.

## FDE Brain Note Rules

`FDE Brain` is Obsidian-native Markdown.

It should use:

- Obsidian Properties/frontmatter
- wikilinks
- aliases
- tags
- links to headings
- explicit related-note sections where useful
- provenance inside notes

It should not contain:

- drafts
- temporary notes
- raw source dumps
- one-note-per-source imports
- generated Graphify Obsidian exports

Final notes are created only when a stable or reusable concept emerges.

## FDE Brain Note Shape

Final notes do not need an identical template, but should satisfy a minimum standard.

Example:

```markdown
---
type: pattern
status: stable
tags:
  - type/pattern
  - status/stable
aliases:
  - RAG eval pattern
sources:
  - raw: AI Space/raw/books/example.pdf
    normalized: AI Space/normalized/books/example/chapter-03.md
    locator: "chapter 3 > Retrieval Quality"
    supports:
      - "failure classes for RAG evaluation"
      - "groundedness testing checklist"
created: 2026-05-21
updated: 2026-05-21
---

# RAG Evaluation Pattern

## Summary

Short compiled summary.

## Core Idea

Compiled knowledge.

## Practical Use

How this applies to Forward Deployed AI Engineering.

## Related

- [[LLM Evaluation]]
- [[Retrieval Quality]]

## Source Notes

- `AI Space/raw/books/example.pdf`, chapter 3.
- `AI Space/normalized/books/example/chapter-03.md#retrieval-quality`.
```

## Provenance

Provenance must be precompiled into final notes.

When an agent reads a final note, it should already know which raw and normalized sources support the note. It should not have to perform reverse graph traversal for routine citations.

Required provenance fields for important claims:

- raw source path
- normalized source path
- locator, such as chapter, section, heading, page, or line
- short description of supported claims

If an agent cannot reconstruct provenance for a claim, it must not add that claim as stable knowledge. It should move the item to review.

## Query And Retrieval Protocol

Normal query:

```text
1. Query Brain Graph.
2. Read relevant Markdown notes in FDE Brain.
3. Answer from the real notes.
4. Cite note, section, and precompiled note sources.
```

When Brain Graph is insufficient:

```text
1. Query Source Graph.
2. Read relevant normalized source segments.
3. Answer with citations.
4. Promote stable/reusable knowledge into FDE Brain in the same turn.
5. Update Brain Graph or mark it stale.
6. Log the promotion.
7. Commit.
```

The agent must not answer solely from Graphify output. Graphify identifies candidate files and relationships; Markdown files provide the answer.

## Query-Driven Promotion

If a user question requires `AI Space/normalized`, then the used source has proven practical value.

The agent must integrate the stable/reusable part of that source into `FDE Brain` before finishing the same turn.

This creates the feedback loop:

```text
real question -> Source Graph retrieval -> answer -> same-turn compilation -> better Brain Graph
```

## Citations

Every knowledge-base answer must cite sources.

Citation granularity should be as fine as available:

- final note and heading
- normalized source file and heading/chapter/section
- raw source and page/chapter when available
- URL and access date for web sources

If only coarse citation is available, the answer must say so.

## Graphify Design

Use two Graphify graphs:

```text
AI Space/graph/brain/
  indexes FDE Brain

AI Space/graph/sources/
  indexes AI Space/normalized
```

Allowed uses:

- `graphify query`
- `graphify path`
- `graphify explain`
- `graphify extract --backend claude`
- Graphify MCP where supported
- HTML/wiki exports for debugging outside `FDE Brain`

Forbidden use:

- writing `graphify --obsidian` output into `FDE Brain`

Graph staleness must be explicit. If graph refresh fails after file changes, write a stale marker and log the reason.

## Logs

Expected log areas:

```text
AI Space/logs/runs/
AI Space/logs/decisions/
AI Space/logs/errors/
AI Space/logs/promotions/
```

Run logs should include:

- batch ID
- start/end time
- files found in pending
- files archived
- normalized outputs created
- final notes created or updated
- graphs updated
- review/failed items
- commit hash

Decision logs should include:

- why a source created a note
- why a source updated an existing note
- why a source did not enter `FDE Brain`
- which patterns were extracted
- conflicts or contradictions found

Promotion logs should include:

- source used
- question or trigger
- final note created or updated
- citations added
- graph update status

Error logs should include:

- parser failures
- OCR failures
- Graphify failures
- unreadable files
- commit failures

## Review And Failed Areas

Review areas:

```text
AI Space/review/ambiguous/
AI Space/review/conflicts/
AI Space/review/needs-human/
AI Space/review/low-confidence-normalization/
```

Failed areas:

```text
AI Space/failed/technical-failures/
```

Review is for judgment problems. Failed is for technical failures.

## Git Safety

The workspace should be a git repository.

Rules:

- commit after each successful ingestion run
- commit after query-driven promotion
- commit partial-success runs if processed items were safely archived and logs record failures
- do not clean `pending` if safe archiving did not complete
- never permanently delete original sources
- use git rollback if a run damages `FDE Brain`

## Automation Modes

### Scheduled Ingestion

Primary daily run, executed by Claude Code through Windows Task Scheduler or an equivalent local scheduler.

### Manual Run

Same pipeline, triggered manually by the user or Codex.

### Query-Time Promotion

Triggered during a user conversation when Source Graph is needed.

### Maintenance / Lint

Periodic review for:

- broken links
- duplicate notes
- missing provenance
- orphan notes
- stale graphs
- unused normalized sources
- duplicate patterns
- contradictions
- incoherent tags
- notes that are too long
- raw files with failed or low-quality normalization

### Recovery

Manual mode for:

- retrying `failed`
- reviewing `review`
- regenerating Graphify
- rebuilding registries
- rolling back through git

## Multi-Agent Protocol

Both Claude Code and Codex must be able to query and maintain the system.

Shared rules live in:

```text
AI Space/system/AGENT_PROTOCOL.md
```

Agent-specific entrypoints may exist:

```text
CLAUDE.md
AGENTS.md
```

Those files should point to the shared protocol rather than duplicate all logic.

## Success Criteria

The system is successful when:

- `pending` can be used without user-side structure.
- scheduled ingestion leaves `pending` empty after safe processing.
- original files are preserved.
- normalized sources are searchable and citably segmented.
- `FDE Brain` remains clean, compiled, and Obsidian-native.
- Graphify helps agents find relevant files without large token scans.
- both Claude Code and Codex can answer using the same retrieval protocol.
- source-only knowledge used in answers is promoted into `FDE Brain` in the same turn.
- every knowledge-base answer cites sources.
- every run is auditable through logs and git commits.

## Open Implementation Decisions

These are implementation details, not unresolved design requirements:

- exact folder naming convention inside `raw`
- exact normalized source registry format
- exact Graphify command wrapper
- exact Windows Task Scheduler command
- exact GLM-OCR invocation through Ollama
- exact git commit message format
- exact stale marker filename and contents
