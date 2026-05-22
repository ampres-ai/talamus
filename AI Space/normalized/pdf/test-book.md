---
source-path: AI Space/raw/pdf/2026-05-22-test-book.pdf
source-type: pdf
source-hash: sha256:860186114a75a264c4a05f87cd20a6a67d637c123a9b0525a847b1387b248b87
captured-at: 2026-05-22T16:30:25.022902+00:00
parser: pypdf
parser-confidence: 1.0
---

# 2026-05-22-test-book

## Chapter 1: Foundations of Retrieval

_Pages 1–5_

Chapter 1: Foundations of Retrieval
Retrieval-augmented generation pairs an LLM with an external index.
Documents are chunked, embedded, and stored in a vector database.
Query embeddings find the nearest chunks, which become extra context.
Pitfall: shallow chunks miss the surrounding argument; deep chunks waste tokens.
Practical rule: chunk to natural section boundaries, not fixed token counts.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

## Chapter 2: Knowledge Graph Routing

_Pages 6–10_

Chapter 2: Knowledge Graph Routing
Vector search answers 'similar to' but not 'related to'.
Knowledge graphs encode typed relations, allowing multi-hop reasoning.
Hybrid: vector finds candidates, graph filters and orders them by relation.
Build graphs from sources (extracted entities) and from curated notes (Brain Graph).
Refresh the graph after each ingestion; otherwise routing drifts.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

## Chapter 3: Provenance and Trust

_Pages 11–15_

Chapter 3: Provenance and Trust
Every answer should carry a fine-grained citation.
Fine-grained means heading anchor or paragraph, not just file path.
When the model paraphrases, the citation lets a human verify.
Provenance also enables incremental refresh: only invalidate notes whose sources changed.
Pattern: store source_hash in the curated note frontmatter.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

## Chapter 4: Operational Hygiene

_Pages 16–20_

Chapter 4: Operational Hygiene
Run ingestion on a schedule, not ad hoc.
Log every decision: what was promoted, what was skipped, why.
Failures route to a review queue; nothing is silently dropped.
Treat the wiki as code: git tracks every change, including the graph snapshot.
Quarterly: walk through review/needs-human and decide each entry.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

This paragraph extends the chapter so that the synthetic book comfortably crosses the long-PDF
threshold and exercises the multi-page extraction path. It carries no specific signal beyond filler.

