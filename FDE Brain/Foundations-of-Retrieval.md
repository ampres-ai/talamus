---
type: chapter
tags: [rag, retrieval, embeddings, vector-search, chunking]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-1-foundations-of-retrieval
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Foundations of Retrieval

Retrieval-augmented generation (RAG) pairs a large language model with an external index to ground its answers in real documents.

## Core pipeline

1. **Chunking** â€“ source documents are split into smaller passages.
2. **Embedding** â€“ each chunk is mapped to a dense vector via an embedding model.
3. **Indexing** â€“ vectors are stored in a vector database (e.g., FAISS, Pinecone, Weaviate).
4. **Query embedding** â€“ at inference time the user query is embedded with the same model.
5. **Retrieval** â€“ nearest-neighbour search returns the top-k chunks.
6. **Augmented generation** â€“ retrieved chunks are injected into the LLM prompt as extra context.

## Chunking trade-offs

| Strategy | Pro | Con |
|---|---|---|
| Fixed token window | Simple to implement | Cuts mid-argument, loses coherence |
| Natural section boundaries | Preserves logical units | Variable size, may exceed context budget |

**Practical rule:** chunk to natural section boundaries (headings, paragraphs, list blocks) rather than fixed token counts. Shallow chunks miss surrounding argument; overly deep chunks waste tokens and dilute relevance.

## Key takeaway

The quality of a RAG system is bounded by retrieval quality. If the right chunk never surfaces, the LLM cannot compensate. Invest in chunking strategy and embedding choice before tuning the generation prompt.

See also: [[Chunking Strategies]], [[Vector Search]].
