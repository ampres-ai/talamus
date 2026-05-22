---
type: concept
tags: [chunking, rag, text-splitting]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-1-foundations-of-retrieval
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Chunking Strategies

Chunking is the process of splitting source documents into passages before embedding.

## Fixed-size vs boundary-aware

- **Fixed token count** â€“ easy to implement but frequently splits sentences or arguments mid-flow, producing chunks that lack self-contained meaning.
- **Section-boundary chunking** â€“ aligns splits to headings, paragraphs, or logical breaks. Produces variable-length chunks but preserves coherence.

## Practical guidance

Prefer natural section boundaries. When sections are too large, use a sliding window with overlap (e.g., 20 % overlap) to avoid hard cuts. Always verify chunk quality by spot-checking retrieved results against real queries.

Shallow chunks miss the surrounding argument; deep chunks waste tokens and dilute the signal the LLM receives.

See also: [[Foundations of Retrieval]], [[Vector Search]].
