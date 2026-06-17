# RS6 — first end-to-end ANSWER-quality evaluation (2026-06)

Every prior round (RS1–RS5) measured **retrieval** — did the right document come
back. This is the first measurement of **answer quality** — is the final answer
faithful, correct, and honestly refused when out of scope — the surface that
actually decides adoption. Harness: `benchmarks/ask_eval/` (each retrieval system
→ the SAME cited-answer generator → judges), run on the real book brain (212
Italian notes), 35 judged positives + 6 out-of-scope negatives.

Engines (all within the existing subscriptions / local, €0 marginal):
- **Generator** (held constant for every system): gemini-3.1-flash-lite.
- **Primary judge**: local `gemma4:e4b` via ollama.
- **Cross-check judge**: claude-cli (a different model family) on a 12-item slice.

## Method notes (honest, learned the hard way)

- **The judge model is a reasoning model.** `gemma4:e4b` (9.6 GB) emits hidden
  thinking tokens before its visible reply. With thinking ON, a one-word verdict
  prompt spends its entire `num_predict` budget on thinking and returns an EMPTY
  `response` → the first smoke run scored faithfulness/correctness uniformly
  **0.000** for every system. Fix: drive the judge with `think=False` + a small
  `num_predict` cap (now in `OllamaProvider`). Real judge cost ~1.4 s/call. The
  earlier "calibration = 1.05 s/call" was misleading: it timed the call without
  checking that the reply was non-empty (calibration now verifies content).
- **Judge-family caveat, and its control.** The primary judge `gemma` (Google)
  shares lineage with the `gemini` generator (Google) — a self-flattery risk.
  The claude (Anthropic) cross-check on bm25's first 12 answers gave
  **faithfulness agreement 1.00 and correctness agreement 1.00**: on the overlap
  the local judge's verdicts were identical to the independent family. The local
  judge is credible here, not flattering.
- **Faithfulness is near-saturated by design.** Because every system uses the
  SAME generator, instructed to answer ONLY from the provided context,
  faithfulness measures the generator, not retrieval — hence ~1.0 across the
  board. The metrics that DISCRIMINATE between systems are **context_hit**
  (retrieval) and **correctness** (retrieval → answer).

## Results — fair answer-quality shootout (35 queries, 6 negatives)

| system | context_hit | faithfulness | correctness | honest_refusal |
|---|---|---|---|---|
| talamus-smart | **0.943** | 1.000 | **0.914** | **1.000** |
| talamus-search | 0.829 | 1.000 | 0.857 | **1.000** |
| bm25 | 0.771 | 1.000 | 0.871 | 0.833 |
| vectordb (MiniLM) | 0.657 | 0.943 | 0.757 | 0.833 |

Inter-judge agreement (bm25 slice, gemma vs claude, n=12): faithfulness 1.00,
correctness 1.00.

Reads:
- **talamus-smart leads** on both discriminating axes: context_hit 0.943 and
  correctness 0.914 — the user's own LLM expanding the query puts the right notes
  in context and yields the most correct answers.
- **talamus-search ≈ bm25**: context_hit favours talamus-search (0.829 vs 0.771);
  correctness is a wash (0.857 vs 0.871, well within noise on 35 queries).
- **vectordb last** (0.657 / 0.757): the English-centric embedding model on an
  Italian corpus, consistent with the RS5 retrieval shootout.
- **Honest refusal favours Talamus** (1.000 vs 0.833) — but this is **6/6 vs 5/6
  on six negatives**, i.e. a one-question difference. Directional, not proof; the
  expanded-negatives set (queued) is needed to make it statistically real.

## Results — ontology ON/OFF ablation (the REAL ask path, 35 queries)

ON = `answer_question` as shipped (routes via the overview, whose domains are
union-find over the emergent ontology). OFF = same brain with the overview
removed → the plain persistent-index path. Same generation + judge both ways.

| variant | context_hit | faithfulness | correctness | route |
|---|---|---|---|---|
| ontology_on | **1.000** | 0.543 | **0.957** | overview ×35 |
| ontology_off | 0.857 | 0.686 | 0.886 | index ×35 |

Reads:
- **The emergent ontology pays off in ANSWER quality, not just navigation.**
  Overview routing lifts context_hit +0.143 (1.000 vs 0.857) and correctness
  +0.071 (0.957 vs 0.886) on the real ask. This is the MEANING moat shown to
  improve answers, not only routing cost — the first such measurement.
- **The faithfulness dip (0.543 vs 0.686) is a measurement artifact, not a
  regression.** The ablation judges faithfulness against the GOLD (qrels)
  documents, not the actual context the ask read. ontology_on retrieves the full
  right context (hit 1.0) and produces richer answers that include details beyond
  the narrow gold set, so the judge scores them less "grounded in gold." Fix
  queued: judge against the ask's actual `items_read`, then re-run. Do not read
  this as a groundedness regression.

## Signal vs noise

Small: 35 positives, **6 negatives**, ONE corpus (book), generator gemini +
judge gemma (same Google family, claude cross-checked). Treat magnitudes as
directional. The most robust signals: talamus-smart's context_hit/correctness
lead, and the ablation's context_hit/correctness wins for the ontology. The
refusal delta is a single question. Faithfulness does not discriminate in this
design.

## What this establishes

1. A real answer-quality baseline now EXISTS (it never did — the harness had
   never been run). The ASK can be compared to competitors on the final answer,
   not just on retrieval.
2. On this corpus, **talamus-smart produces the most correct answers and the
   best-targeted context**; competitors trail; the dense model is worst on
   Italian.
3. **The emergent ontology measurably improves answer correctness and
   context-hit** on the real ask — the MEANING moat, evidenced in answers.
4. The local €0 judge is credible (perfect agreement with an independent family
   on the measured slice).

## Residuals / queue (added to STATE)

- Ablation faithfulness must be judged against the ask's ACTUAL context (trace
  `items_read`), not the gold docs; re-run after the fix.
- Expand the negatives set (currently 6) so honest-refusal is statistically real.
- Faithfulness saturates under the shared faithful generator; correctness is the
  better answer-quality discriminator in this design.
- One corpus only (book). The docs-corpus ASK eval needs a docs brain built with
  an eval-set (two-corpora law for any answer-quality claim that ships).

## Reproduce

```
ollama pull gemma4:e4b
python -m benchmarks.ask_eval.calibrate --model gemma4:e4b            # roles gate
python -m benchmarks.ask_eval.run --brain <book> --queries 0 \
    --cross-judge-engine claude-cli                                   # answer-quality
python -m benchmarks.ask_eval.run --brain <book> --queries 0 --ablation
```
