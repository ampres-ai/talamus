# RS8 — zero-subscription local engine, smart cost, and honest refusal (2026-06)

The remaining BEAT levers after the adaptive trigram win (#1): the
zero-subscription local pipeline (#4), smart-expansion stability/cost (#3), and
refusal-as-weapon (#2). Method stays measure-first.

## #4 — fully-local €0 pipeline (ollama gemma4:e4b as BOTH generator and judge)

Book, 10 stratified queries + 6 negatives, generator = judge = `gemma4:e4b`
(nothing leaves the machine, €0 marginal):

| system | context_hit | faithfulness | correctness | honest_refusal |
|---|---|---|---|---|
| talamus-search | 0.800 | 0.800 | **0.800** | 1.000 |
| bm25 | 0.900 | 0.700 | 0.700 | 1.000 |
| talamus-smart | 0.700 | 0.700 | 0.700 | 1.000 |
| vectordb | 0.500 | 0.500 | 0.500 | 0.833 |

Reference: with the cloud generator (gemini-flash-lite, RS6, 35q) talamus-search
correctness was 0.857. Fully local it is 0.800 — a modest drop on a much smaller,
noisier sample.

**The zero-subscription promise holds on quality**: a small local model runs the
whole pipeline and produces correct, grounded, cited answers (~0.80 on
talamus-search), with the local judge confirming it. This is the PRODUCT.md bar
"works with a small local model" — met, with one honest caveat below. (PRODUCT.md
edit is proposed, not applied — needs maintainer approval.)

### The caveat, measured: generation latency

**5 of 40 generations (~12.5%) exceeded the 90 s hard timeout** — `gemma4:e4b`
(a 9.6 GB reasoning model) thinks too long on CPU for some prompts, and the
`TimeoutLLM` wrapper abandons the call (the answer is then empty → scored wrong).
So local generation is viable but latency-unreliable. This is the SAME risk
already queued for the product `talamus ask` (gemini-on-Windows hang): **a hard
per-call timeout belongs in the engine adapter**, and for slow local models the
mitigations are a larger timeout, a smaller/faster model, or `think=False` for
generation (faster, quality untested).

### #3 corollary, measured: smart INVERTS on a slow local engine

talamus-smart (0.700) scored BELOW talamus-search (0.800) here — the opposite of
the cloud result (smart leads). Reason: smart adds an LLM query-expansion call per
query, doubling exposure to the slow/timeout-prone local generation. **On a slow
local engine, plain search beats smart.** smart's value is real with a fast
(cloud) engine; with a slow local one its extra call is a net negative. The
multi-pass union (#3, shipped, opt-in) is therefore for cloud/sampling engines,
not for slow local ones — documented.

## #2 — refusal-as-weapon: measured, already a Talamus strength, no gate shipped

Across BOTH the cloud (RS6 gemini) and the fully-local (this) runs, on the 6
out-of-scope negatives:

| | talamus-search | talamus-smart | bm25 | vectordb |
|---|---|---|---|---|
| honest_refusal (gemini gen) | 1.000 | 1.000 | 0.833 | 0.833 |
| honest_refusal (ollama gen) | 1.000 | 1.000 | 1.000 | 0.833 |

Talamus refuses out-of-scope questions perfectly and engine-independently: its
retrieval returns nothing for a truly off-topic query, so the answer honestly
declines. **The differentiator already exists by construction** — adding a
coverage-score gate to `answer_question` (the planned #2 lever) is unnecessary and
would have been a fragile change (the blended/length-penalised score has no stable
absolute threshold across corpora). So #2 ships NO code: we measured, found
Talamus already wins refusal, and did not bolt on a risky gate.

**Honest residual:** 6 negatives is a tiny sample — the 1.000 vs 0.833 gap is a
one-question difference. The real follow-up is a LARGER negatives set (queued), not
a coverage gate.

## Verdict on the four BEAT levers

1. **Adaptive trigram (#1)** — shipped; beats BM25 on SciFact, zero regression
   (see 2026-06-rs8-adaptive-trigram.md).
2. **Refusal (#2)** — measured; already a strength (refusal 1.000), no code; expand
   negatives to confirm.
3. **Smart stability (#3)** — multi-pass union shipped (opt-in); plain search wins
   on slow local engines.
4. **Zero-sub local e2e (#4)** — works (talamus-search correctness 0.800, fully
   €0); caveat = generation latency (12.5% >90 s) → hard timeout belongs in the
   product adapter.

## Artifacts

- `benchmarks/results/2026-06-17-ask-eval-ollama.json` (fully-local run).
- `benchmarks/results/2026-06-17-ask-eval.json` (cloud RS6, gemini, preserved).
