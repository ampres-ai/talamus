---
type: pattern
tags: [provenance, citation, incremental-refresh, frontmatter]
sources:
  - AI Space/normalized/pdf/test-book.md
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Source-Hash Provenance

Store a `source_hash` in every curated note's frontmatter to track provenance.

**Benefits:**
- Enables fine-grained citation (heading/paragraph level, not just file path).
- Supports incremental refresh: only invalidate notes whose source hash has changed.
- Lets a human verify any paraphrased claim back to the original.
