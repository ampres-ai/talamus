---
type: pattern
tags: [operations, ingestion, logging, review-queue]
sources:
  - AI Space/normalized/pdf/test-book.md
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Operational Ingestion Hygiene

Treat wiki ingestion as a production pipeline, not an ad-hoc task.

1. **Schedule** ingestion runs; do not rely on manual triggers.
2. **Log every decision**: what was promoted, skipped, and why.
3. **Route failures** to a review queue â€” never silently drop content.
4. **Version everything** in git, including graph snapshots.
5. **Quarterly review**: walk the `review/needs-human` queue and resolve each entry.
