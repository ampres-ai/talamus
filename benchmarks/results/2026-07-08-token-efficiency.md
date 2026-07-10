# Token efficiency — re-measured 2026-07-08

Command: `python benchmarks/token_efficiency.py C:/dev/_talamus_book`
(tiktoken cl100k_base proxy; brain: 212 notes, enriched+consolidated)

| path | tokens | vs load-all |
|---|---:|---:|
| load-all (whole brain in context) | 113,530 | — |
| recall (avg, targeted) | 2,637 | −97.7% |
| search (avg, titles) | 248 | −99.8% |

Confirms the June headline byte-for-byte on the 2026-07-08 code
(post model_json refactor, post ontology-inference merge pending).
