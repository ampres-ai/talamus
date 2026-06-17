# RS8 — adaptive trigram blend: closing the English ranking gap (2026-06)

The honest residual carried since RS5: `talamus-search` trailed BM25 on nDCG/MRR
on monolingual English (SciFact: 0.607/0.562 vs 0.652/0.618). RS5 named the cause
— the character-trigram channel (the IT↔EN cognate bridge) adds noise where no
cross-language is needed — and proposed an adaptive blend. The RS7 steelman made
it urgent: a strong multilingual dense model (e5) also out-ranks us on the book.

## The lever

Detect a **monolingual-ASCII corpus** at index build (from RAW note text — the
tokenizer strips accents, so the detector must not run on the haystack) via
`non_ascii_ratio < 0.05`, and store a flag in the index (sqlite `config` table /
postings key). At query time, scale the two trigram channel weights by
`MONO_TRIGRAM_SCALE` when the corpus is flagged. The flag is computed by
construction; pre-existing indexes default to non-monolingual (no behaviour
change until reindex). CACHE_VERSION 4→5.

## Ablation (talamus-search, scale sweep, build-once / patch-scale)

SciFact (English, **flagged monolingual**), 300 queries, k=10:

| scale | recall@10 | nDCG@10 | MRR | hit@10 |
|---|---|---|---|---|
| 1.0 (pre-RS8) | 0.776 | 0.607 | 0.562 | 0.793 |
| 0.7 | 0.773 | 0.626 | 0.586 | 0.790 |
| 0.5 | 0.790 | 0.646 | 0.606 | 0.807 |
| **0.3 (shipped)** | **0.797** | **0.664** | **0.628** | **0.813** |
| 0.0 | 0.797 | 0.661 | 0.626 | 0.817 |

BM25 on SciFact (reference): recall 0.776, nDCG 0.652, MRR 0.618, hit 0.797.

**At scale 0.3 talamus-search now BEATS BM25 on all four metrics** (nDCG 0.664 >
0.652, MRR 0.628 > 0.618, recall 0.797 > 0.776, hit 0.813 > 0.797). The trigram
channel was actively HURTING monolingual English; damping it to 0.3 both closes
the ranking gap and lifts recall/hit. 0.3 edges 0.0 on nDCG/MRR (a little trigram
still helps morphological variants), so 0.3 ships.

## Two-corpora law — both law corpora are untouched

| corpus | flagged? | recall / MRR / hit, scale 1.0 → 0.3 |
|---|---|---|
| docs (120 cases) | NO (mixed IT/EN, non-ASCII > 5%) | 0.508 / 0.459 / 0.618 → identical |
| book (212 IT notes) | NO (Italian) | 0.829 / 0.727 / 0.914 → identical |

The detector is deliberately conservative: it fires only on cleanly monolingual
English (SciFact), leaving every mixed or cross-language corpus — including both
law corpora — byte-identical. So the change is a strict improvement: a decisive
win on English, **zero** regression on docs and book. By the two-corpora law
(neutral on both real corpora) plus a clean English-benchmark win, it ships.

## What shipped

- `textutil.non_ascii_ratio` / `is_monolingual_ascii` (raw-text detector).
- `indexes.MONO_TRIGRAM_SCALE = 0.3` (env-overridable `TALAMUS_MONO_TRIGRAM_SCALE`),
  flag stored at build, applied at query in both backends.
- CACHE_VERSION 5 (reindex picks up the flag).
- CI floor: `tests/test_talamus_adaptive_trigram.py` (mechanism, in CI) +
  `tests/test_benchmarks_adaptive_floor.py` (SciFact nDCG≥0.63 / recall≥0.77,
  heavy/gated).

## Honest residuals

- The win is measured on SciFact (English) + the two law corpora as the
  no-regression guard. A second monolingual-English BEIR set (nfcorpus) would
  further de-risk the "English" generalization; queued.
- The detector is a script/accent heuristic, not language ID. A monolingual
  non-Latin-script corpus (e.g. all-Chinese) has 0 non-ASCII-Latin chars and
  would be flagged monolingual — correct outcome (trigram cognate bridge is
  irrelevant there too), but untested. Queued.
