---
type: chapter
tags: [provenance, citations, trust, incremental-refresh]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-3-provenance-and-trust
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Provenance and Trust

Every answer a knowledge system produces should carry a **fine-grained citation**â€”heading anchor or paragraph-level, not just a file path. This serves two purposes:

1. **Human verification.** When a model paraphrases source material, the citation gives a reader a direct path back to the original text to confirm accuracy.
2. **Incremental refresh.** Provenance metadata enables selective invalidation: only curated notes whose underlying sources actually changed need to be re-processed.

### Implementation pattern

Store a `source_hash` in the frontmatter of each curated note. On re-ingestion, compare the hash of the current source chunk against the stored value. If they match, skip distillation. If they diverge, re-distill and update the note.

This keeps the wiki both **trustworthy** (every claim is traceable) and **efficient** (unchanged material is never redundantly reprocessed).
