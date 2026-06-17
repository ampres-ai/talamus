# RS7 — competitive expansion: the honest steelman (2026-06)

RS5 reported the dense vector DB LAST on the book (cross-language/vague): recall
0.700, hit 0.743. But that competitor was `all-MiniLM-L6-v2` — an English-centric
model. The obvious critique: "you beat a weak baseline." RS7 answers it by adding
the steelman — a STRONG multilingual embedding model — and running it on the same
book corpus.

## The steelman result (book, 212 IT notes, 35 judged queries, k=10)

| system | recall@10 | nDCG@10 | MRR | hit@10 | cost |
|---|---|---|---|---|---|
| talamus-smart | 0.886 | 0.783 | 0.796 | **0.971** | ~14 s/query (LLM) |
| **dense-multilingual (e5)** | 0.871 | **0.837** | **0.857** | 0.914 | 74 ms + ~1 GB model in RAM |
| talamus-search | 0.829 | 0.732 | 0.727 | 0.914 | 11 ms, zero infra |
| bm25 | 0.771 | 0.688 | 0.685 | 0.829 | 0.6 ms |
| vectordb (MiniLM) | 0.700 | 0.565 | 0.535 | 0.743 | 11 ms |

**The uncomfortable, honest finding:** a strong multilingual dense model
(`intfloat/multilingual-e5-base`) does NOT collapse on our cross-language corpus.
It LEADS on ranking quality (nDCG 0.837, MRR 0.857 — above even talamus-smart's
0.783/0.796) and out-recalls talamus-search. talamus-smart keeps the best hit
(0.971) and recall (0.886), but only with a ~14 s/query LLM call. talamus-search
(zero infra, 11 ms) trails e5 on every metric except a hit tie.

**What this corrects:** RS5's "we beat dense on cross-language" was an artifact of
the weak English-centric MiniLM. Against a real multilingual embedding model we do
NOT win cross-language retrieval outright. The defensible Talamus edge is:
- **zero embedding infrastructure** (no 1 GB model in RAM, no GPU, no encode pass
  at ingest, €0) at competitive — not superior — retrieval;
- the **moats** (time / meaning / verifiability) e5 has none of;
- **answer quality** (RS6: talamus-smart correctness 0.914, honest refusal, the
  ontology lifting answers) — the surface that actually decides adoption.

The steelman did its job: it moved a marketing claim back to what the data
supports. We compete on the whole workflow and zero-infra ownership, not on
beating embeddings at raw ranking.

## MIRACL (large multilingual judged set) — ABANDONED

Planned as the large cross-language set to de-noise the n=4 book claim, but
abandoned for two reasons. First, **MIRACL has no Italian** and is
multilingual-MONOLINGUAL (query and docs share a language) — NOT cross-language,
so it does not serve the original purpose; the book stays the cross-language test.
Second, it is impractical here: the MIRACL HF repo ships a loading SCRIPT (needs
`datasets<3`, since v3+ removed scripts) and the per-language corpus download is
large and throttled without an HF token. The steelman finding above already
establishes the key result, so MIRACL added no value worth the cost. The loader,
its test, and the `datasets` dependency were removed.

## Infrastructure added (bench-only, deps never in product core)

- `MultilingualDenseSystem` (e5 with the required query/passage prefixes).
- `LLMWikiSystem` (LLM keyword augmentation at ingest, retrieval over augmented
  text; pointed at the local engine for €0; faithful minimal stand-in for the
  hosted-API-locked upstream).
- Agent-memory benchmark scaffold (`agent_mem/`, store→recall, mem0's real turf;
  heavy mem0 runner pending).
- CI negatives set (8 IT/EN out-of-scope questions).

## Queue

- nfcorpus (2nd English BEIR) for parity robustness.
- agent-memory heavy run (mem0 local vs Talamus recall).
- The steelman finding should temper README/marketing language about cross-language.
