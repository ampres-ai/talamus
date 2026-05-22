---
type: pattern
tags: [retrieval, knowledge-graph, vector-search, RAG]
sources:
  - AI Space/normalized/pdf/test-book.md
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Hybrid Retrieval Pattern

Combine vector search with knowledge-graph routing for richer retrieval.

1. **Vector search** finds semantically similar candidate chunks.
2. **Knowledge graph** filters and re-ranks candidates by typed relations, enabling multi-hop reasoning.

Vector answers *"similar to"*; the graph answers *"related to"*. Using both covers similarity **and** structural relevance.
