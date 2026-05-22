---
type: concept
tags: [vector-search, embeddings, nearest-neighbour, rag]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-1-foundations-of-retrieval
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Vector Search

Vector search (nearest-neighbour search) is the retrieval step in a RAG pipeline. Query and document chunks are represented as dense vectors; the system returns chunks whose embeddings are closest to the query embedding, typically by cosine similarity or inner product.

## Why it matters

Vector search replaces keyword matching with semantic matching. A query about "scaling web services" can surface a chunk that never mentions those exact words but discusses load balancing and horizontal scaling.

## Pitfalls

- Embedding model mismatch: using different models for documents and queries produces incompatible vector spaces.
- Dimensionality vs cost: higher-dimensional embeddings capture more nuance but increase storage and latency.

See also: [[Foundations of Retrieval]], [[Chunking Strategies]].
