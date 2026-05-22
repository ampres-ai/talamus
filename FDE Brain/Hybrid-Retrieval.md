---
type: concept
tags: [retrieval, hybrid-search, architecture-pattern]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-2-knowledge-graph-routing
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Hybrid Retrieval

A two-stage retrieval pattern that pairs a fast, recall-oriented first pass (typically vector/embedding search) with a precision-oriented second pass (graph filtering, re-ranking, or structured constraint checking).

In the context of [[Knowledge Graph Routing]], the vector store supplies candidates ranked by similarity, and the knowledge graph prunes and reorders them by relational validity. The key advantage is that neither system alone covers both similarity *and* relational queries well, but composed they do.

Design consideration: the candidate set from stage one must be large enough that stage two has room to reorder, but small enough to keep graph traversal fast. Typical ratios are 5â€“10Ã— the final top-k.
