# Ontology inference layer — design (F2-B, ruled A+B+C 2026-07-07)

The level-jump for MEANING. Grounded in two measured facts: the ontology
already lifts ANSWERS (ask ablation: context_hit 0.857→1.000, correctness
0.886→0.957), and every attempt to push graph signals into SCORING failed
(rejected with data: score propagation −2pt, triangulation hub pollution,
1-hop seed swap no-lift). Therefore:

## Principle 1 — closure, not scoring

Inference produces NEW DERIVED EDGES (a cache layer, rebuildable), never a
ranking-score term. Consumers are structure and context: `neighbors`, the ask
context bundle (flag-gated, ablation-measured), the insights surface (F2-A).

## Principle 2 — type algebra induced from evidence, promoted like types

Each ACTIVE relation type may earn properties: `inverse_of: <type>`,
`transitive: bool`, `symmetric: bool`. Properties are INDUCED, never
hand-coded, and go through the existing candidate → review → promote
lifecycle (same philosophy, same versioned schema events):

- **inverse candidate**: types T and U where ≥k pairs (A-T→B and B-U→A) with
  the same endpoints co-occur (the wild already produced rel:reports /
  rel:is-reported-by). Propose `inverse_of` with the support list.
- **transitive candidate**: type T where ≥k chains (A-T→B, B-T→C) ALSO have an
  explicit A-T→C somewhere in the corpus — the corpus itself witnesses the
  property. Without witnesses, never propose.
- **symmetric candidate**: ≥k unordered pairs present in both directions.

Thresholds mirror the type-promotion rules (support ≥8 evidence pairs,
≥3 distinct notes) until measured otherwise.

## Principle 3 — every inferred edge carries provenance

`{source: A, relation: T, target: C, inferred: true, rule: "transitive",
via: [edge_id_1, edge_id_2], schema_version: N}` — the VERIFIABILITY moat
extends to the graph. The UI/MCP can show WHY an edge exists. Inferred edges
live in a derived cache (`.talamus/cache/ontology_inferred.json`), rebuilt by
reindex, never written into notes.

## Consumers (in shipping order)

1. `neighbors` (CLI + MCP + graph service): inferred edges included, marked,
   with the derivation; opt-out flag.
2. Insights (F2-A surface): "surprising links" = inferred edges whose
   endpoints share no domain and no explicit edge; "coverage gaps" = active
   types with support concentrated in one domain; both exposed via a
   `services/ontology.py` insights function → MCP tool + UI panel.
3. Ask context (LAST, flag-gated): inferred neighbors join the bundle only if
   the two-corpora ablation wins (retrieval_lab + ask-eval ON/OFF). A loss is
   recorded in STATE and the flag stays off.

## Acceptance

- Unit: induction proposes inverse/transitive/symmetric ONLY with witnesses;
  promotion writes schema events; closure is deterministic and cycle-safe
  (depth cap 2 for transitive chains at first).
- Ablation: `neighbors`-in-ask ON/OFF on book + docs corpora; ship rule per
  the two-corpora law.
- The hostile-model battery is untouched (no new LLM calls in the closure —
  induction is purely structural over existing evidence).

## Non-goals (this round)

No new LLM calls; no scoring changes; no cross-brain aggregation (that is
F2-C, after this lands); no schema auto-promotion without review.
