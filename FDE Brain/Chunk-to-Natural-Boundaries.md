---
type: pattern
tags: [chunking, RAG, ingestion]
sources:
  - AI Space/normalized/pdf/test-book.md
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Chunk to Natural Boundaries

When splitting documents for embedding, chunk along natural section boundaries (headings, paragraphs, logical breaks) rather than fixed token counts.

- **Shallow chunks** lose the surrounding argument and context.
- **Deep chunks** waste tokens and dilute relevance.
- Natural boundaries preserve coherent reasoning units.
