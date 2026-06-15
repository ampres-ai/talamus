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
