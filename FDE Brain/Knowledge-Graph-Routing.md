---
type: chapter
tags: [retrieval, knowledge-graph, vector-search, hybrid-search]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-2-knowledge-graph-routing
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Knowledge Graph Routing

Vector search retrieves documents that are *similar to* a query, but similarity alone cannot answer questions about typed relationshipsâ€”authorship, dependency, causality, sequence. Knowledge graphs fill that gap by encoding explicit, typed relations between entities, enabling multi-hop reasoning that pure embedding lookups cannot perform.

## Hybrid retrieval pattern

The practical architecture combines both approaches:

1. **Vector candidate generation** â€” an embedding search produces a broad candidate set ranked by cosine similarity.
2. **Graph filtering and ordering** â€” the knowledge graph prunes candidates that lack a valid relational path to the query context and re-ranks survivors by relation type and hop distance.

This two-stage pipeline keeps latency acceptable (vector search is fast) while dramatically improving precision on relational queries.

## Graph construction sources

Graphs are built from two complementary inputs:

- **Extracted entities** â€” NER and relation extraction over raw ingested sources produce an automatically generated graph.
- **Curated notes (Brain Graph)** â€” manually or semi-automatically maintained wiki links and metadata contribute high-confidence edges that anchor the automatic graph.

## Maintenance discipline

The graph must be refreshed after every ingestion cycle. Stale graphs cause routing drift: new content is indexed in the vector store but invisible to the graph filter, so relational queries silently ignore it. Treating graph refresh as a post-ingestion hook rather than a periodic batch job keeps the two retrieval layers in sync.
