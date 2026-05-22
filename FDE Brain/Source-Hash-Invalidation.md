---
type: concept
tags: [incremental-refresh, hashing, performance]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-3-provenance-and-trust
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Source Hash Invalidation

Store a `source_hash` in each curated note's frontmatter. During re-ingestion, hash the current source chunk and compare:

- **Match â†’** skip distillation (content unchanged).
- **Mismatch â†’** re-distill and overwrite the note.

This turns a full re-processing sweep into an incremental one, saving LLM calls proportional to the fraction of sources that actually changed. Pairs naturally with [[Fine-Grained Citation]] since each note already tracks its exact source location.
