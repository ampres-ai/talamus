---
type: glossary
tags: [RAG, LLM, vector-search]
sources:
  - AI Space/normalized/pdf/test-book.md
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Retrieval-Augmented Generation (RAG)

A technique that pairs an LLM with an external index. Documents are chunked, embedded, and stored in a vector database. At query time, the query embedding retrieves the nearest chunks, which are injected as additional context for the LLM's response.
