# The Ontology Lab: a self-emerging type system

The extraction LLM writes **free-form relation surfaces** ("alimenta", "deriva
da", "sostituisce"...). Fixed types (uses / is-a / part-of / contrasts-with /
depends-on) catch some; everything else used to flatten to `related` — lost
meaning. The Ontology Lab recovers it, with review and history.

## The loop

```text
note relations (raw surfaces)
  -> evidence records (deterministic, with provenance)
  -> clusters of unexplained surfaces (stemmed key, support thresholds)
  -> candidate types (named/defined by ONE LLM call)
  -> human review: promote / reject
  -> active schema re-types the concept map
  -> retrieval expands typed edges FIRST -> measurable lift
```

Decisions stay yours: **candidates never touch runtime** until promoted, and
promotion enforces thresholds (support ≥ 8 across ≥ 3 notes by default; `--force`
to override). Types are deprecated, never deleted — the schema itself is
versioned and temporal.

## Commands

```bash
talamus ontology induce            # find candidate types (1 LLM call)
talamus ontology review            # candidates with support + real examples
talamus ontology apply rel:alimenta
talamus ontology status            # schema version, counts, edge coverage
talamus ontology eval --cases f.json   # retrieval lift vs the fixed baseline
talamus ontology stability         # cluster stability (Jaccard) across runs
talamus ontology history | export
```

## Measuring it

- **Coverage** — share of edges with a real type instead of `related`.
- **Lift** — recall/MRR with the active schema vs the fixed baseline, on your own
  eval cases (the same harness as `talamus eval`).
- **Stability** — identical corpus ⇒ identical candidates (deterministic
  clustering; the LLM only names).

Why the ontology is built this way — induced from evidence, promoted only by
measured rules — is covered in [Design principles](design-principles.md).
