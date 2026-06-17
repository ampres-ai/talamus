# Retrieval shootout

commit `e65a245` · 2026-06-17T15:21:44 · 212 docs · 35 queries · k=10

| system | recall@k | MRR | hit | nDCG | p50 ms | ingest LLM calls |
| --- | --- | --- | --- | --- | --- | --- |
| talamus-search | 0.829 | 0.727 | 0.914 | 0.732 | 11.5 | 0 |
| talamus-smart | 0.886 | 0.796 | 0.971 | 0.783 | 14285.1 | 0 |
| bm25 | 0.771 | 0.685 | 0.829 | 0.688 | 0.6 | 0 |
| vectordb | 0.700 | 0.535 | 0.743 | 0.565 | 11.3 | 0 |
| dense-multilingual | 0.871 | 0.857 | 0.914 | 0.837 | 74.4 | 0 |
