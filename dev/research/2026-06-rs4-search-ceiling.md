# RS4 — the search ceiling, and where the LLM earns its keep (2026-06)

Goal of the round: push search hit-rate toward ≥0.92 (the PRODUCT.md bar),
keeping the two-corpora law and no embeddings. Method: error analysis on both
corpora → index-level and ingest-level hypotheses → ablations → only winners
ship.

## Error analysis split search failures into two clean classes

On both corpora the misses are either:

1. **Hub pollution (index-fixable, no semantics needed)** — long "hub" notes
   accumulate blended score across many weak matches and outrank short,
   precisely-titled notes. Clearest on the docs corpus: the giant roadmap
   sections beat the actual "Choose your engine" / "talamus.json" sections.
2. **Pure-semantic vague gaps** — the question shares no useful token or
   trigram with the right note ("voglio spendere meno per far girare il
   modello" → Ottimizzazione dell'inferenza). Only ingest-time semantic
   enrichment (symptom phrasings) can bridge these.

## What shipped (measured wins)

### Hub suppression — mild length penalty (LP=0.5)

`_apply_length_penalty` damps each candidate by haystack length relative to the
candidate-set average. Self-targeting: bites only where lengths vary.

| corpus | hit before | hit after | notes |
|---|---|---|---|
| docs (CI floor) | 0.600 | 0.618 | code +0.07, cross-source +0.05, direct +0.04 |
| book (uniform) | 0.861 | 0.861 | MRR +0.007, neutral |

LP=0.8 starts hurting vague/MRR → 0.5 is the sweet spot. Shipped, CACHE_VERSION 4.

### Symptoms from the note body, not just the summary

The enrich prompt now sees a body extract. A/B on the book (strip + re-enrich):

| variant | hit | vague | vague-en |
|---|---|---|---|
| no symptoms | 0.778 | 0.50 | 0.25 |
| from summary | 0.861 | 0.75 | 0.50 |
| from body (run 1) | 0.917 | 0.88 | 0.75 |
| from body (run 2) | 0.861 | 0.63 | 0.75 |

Body is neutral-to-better and lifts vague-en consistently. Shipped — but see
the variance finding below; the headline 0.917 did not reproduce.

## The ceiling (the real finding)

Two structural limits cap lexical+trigram+symptom search well short of a
reliable 0.92:

1. **Symptom generation is nondeterministic.** Identical procedure, two runs:
   hit 0.861 vs 0.917. The swing is the model picking different phrasings.
2. **Symptom bloat self-pollutes.** Union of N enrichment passes to smooth
   variance: x1 0.861 → x2 **0.889** → x3 0.833. The third pass DROPS the
   score: an over-enriched note carries so many phrases it becomes a
   field-level hub and matches unrelated queries. The same pollution the
   length penalty fights, now inside the note. There is a hard trade-off
   between symptom coverage (recall) and symptom noise (precision), and it
   tops out around 0.89 on a curated brain.

**Conclusion: search (instant, free, no per-query LLM) plateaus at ~0.86–0.89
on a well-curated brain. 0.92 is not reliably reachable by lexical means.**

## Where the LLM earns its keep

The path past the search ceiling is the one already built and measured: the
**ask** path puts the user's LLM in the loop (routing + query expansion +
ranked selection) and reaches **hit 0.972**. Search and ask are different
tools with different ceilings:

- `search`: known-item lookup, milliseconds, zero marginal cost, ~0.86–0.89.
- `ask`: natural-language questions, LLM-in-the-loop, ~0.97.

This validates the original thesis — "the LLM is the embedding model" — but
locates it precisely: it belongs at ask time (and at ingest, via enrichment),
not in a per-query-free search reranker.

## Open question for the product (needs maintainer decision)

The PRODUCT.md bar "search hit ≥0.92" may be targeting the wrong tool. Options:
1. Revise the bar to the measured search ceiling (~0.88) and make `ask` the
   quality promise for natural-language questions (already ≥0.95).
2. Keep 0.92 and find a fundamentally different lexical lever (none found this
   round).
3. Offer opt-in 2-pass enrichment (`--passes 2`, +0.028 hit, doubles ingest
   cost) for users who want maximum search quality — not shipped pending the
   decision above.

## Rejected / not shipped this round (with data)

- Title-coverage boost: helped docs recall but hurt book MRR — not robust.
- BM25 b=0.9: worse than b=0.75 + explicit length penalty.
- 3-pass symptom union: over-dilutes (0.833 < 0.889).
- LP=0.8: hurts vague and MRR.

## Literature review (RS3-lit): no-embedding levers, mapped to Talamus

Surveyed the sparse/lexical retrieval literature for a lever to break the
ceiling without embeddings. Findings, each mapped to what we already do:

| Technique | Literature result | Status for us |
|---|---|---|
| Document expansion (doc2query / docT5query) | +17-20% MRR/MAP on MS MARCO/TREC; two mechanisms — term reweighting (copy 69%) + term injection (31% new) | **We already do this** = symptom enrichment (injection). We omit copy-reweighting on purpose: our hard cases are vague (vocabulary mismatch), where injection is the right half |
| Query expansion w/ LLM (Query2doc) | +3-15% on BM25, no fine-tuning; query-time | **We do it in ask**; tested on pure search below → the winner |
| RM3 / PRF (relevance model) | strong classical baseline | tested (RS2), rejected: vague unchanged, MRR down |
| Field separation (BM25F: symptoms in a separate weighted channel) | motivated by doc2query dilution | **TESTED, rejected**: neutral-to-worse at all weights (0.2-1.0) on the book — does not transfer to small curated brains |
| Term proximity / Sequential Dependence Model | +5-11% MAP on TREC long docs | **TESTED, rejected**: coverage boost helps book (+0.03) but HURTS docs cross-source (0.50→0.45) — fails the two-corpora law; token-bigram proximity neutral on both |
| Learned sparse (SPLADE / DeepCT) | SOTA sparse | rejected by constraint: needs a transformer (embedding-adjacent) |

**Conclusion of the literature review:** the only proven no-embedding lever we
do NOT yet exploit at search time is **Query2doc — LLM query expansion** — and
the literature says it is precisely the technique for the vague/hard queries
that cap us. It is the user's own LLM (constraint-compliant), and it can be
cached.

## The breakthrough: Query2doc on pure search

Measured on the book brain (real index, cached LLM expansions, NO routing —
just expand-the-query + search):

| | hit | recall | MRR | vague | cross |
|---|---|---|---|---|---|
| search baseline | 0.861 | 0.792 | 0.702 | 0.62 | 0.75 |
| search + Query2doc | **0.972** | **0.903** | **0.840** | **1.00** | **1.00** |

+0.111 hit, crossing the ≥0.92 bar decisively; vague 0.62→1.00. The lexical
ceiling is broken by putting the user's LLM in the query path — the original
thesis ("the LLM is the embedding model"), now literature-grounded and proven
on search, not just ask. Cost: one LLM call per unique query (cacheable).

**Two-corpora confirmation (the law):** measured on the docs corpus too
(mechanical, un-enriched, the hard floor; 120 real LLM expansions):

| | hit | recall | MRR | vague | cross-source |
|---|---|---|---|---|---|
| docs baseline | 0.618 | 0.497 | 0.461 | 0.37 | 0.55 |
| docs + Query2doc | **0.782** | **0.621** | **0.576** | **0.70** | **0.75** |

+0.164 hit — the harder corpus gets the bigger lift. Wins decisively on BOTH
corpora (only temporal dips slightly, 0.93→0.80: date questions get diluted by
expansion — a minor known tradeoff).

**Shipped:** `talamus search --smart` (and the MCP `search(smart=True)` tool) —
`smartsearch.expand_query` runs the cached Query2doc expansion, degrades to
plain search on any engine failure. The lexical ceiling is no longer the
product's search ceiling.

## Sources

- Nogueira & Lin, doc2query / docTTTTTquery (arxiv 1904.08375; UWaterloo).
- Wang et al., Query2doc: Query Expansion with LLMs (arxiv 2303.07678).
- Sequence dependence / proximity: Microsoft PPM; Springer proximity-statistic.
- Learned sparse retrieval (SPLADE) — Wikipedia overview + arxiv 2511.22263.
