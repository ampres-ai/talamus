---
type: concept
tags: [knowledge-graph, data-quality, operational-risk]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-2-knowledge-graph-routing
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Graph Routing Drift

When a knowledge graph is not refreshed after new content is ingested into the vector store, relational queries silently degrade. The vector index returns new documents as candidates, but the graph filter discards them because they have no edges. The result: the system behaves as if the new content does not exist for any relation-based query, even though keyword and similarity searches surface it fine.

Mitigation: treat graph rebuild or incremental update as a mandatory post-ingestion hook, never as a separate batch job that runs on its own schedule.
