# Measuring retrieval

Talamus treats retrieval quality as something you **measure**, not guess. The
`talamus eval` command runs a set of questions through the real retriever and reports
recall@k, precision@k, MRR, and hit-rate — so you can tell whether a change (reranking,
a new note, a config tweak) actually helped.

## 1. Write a cases file

A *case* is a question plus the note titles a good retriever should surface. Save a
JSON file — a list, or an object with a `cases` key:

```json
[
  { "question": "how does reranking work?", "relevant": ["Reranking"] },
  { "question": "what stores embeddings for search?", "relevant": ["Vector Store", "Embedding"] }
]
```

Use the real **titles** of notes in your brain (matching is case-insensitive).
`relevant` may list more than one note; a case counts as a hit if any relevant note
appears in the top *k*.

## 2. Run it

```bash
talamus eval --cases cases.json -k 5
```

```text
Illustrative output:

Valutazione recupero — 2 casi, k=5
  recall@5    0.750
  precision@5 0.300
  MRR         0.833
  hit-rate    1.000
  mancati (0):
```

Add `--json` for the full per-case breakdown (handy for scripts and CI).

## 3. Use it to judge changes

Run the same cases **before and after** a change. If recall@k or MRR goes up, keep the
change; if it drops, you caught a regression before it shipped. This is exactly how
Talamus validated its reranking stage — a case that graph-only retrieval ranked wrong,
and reranking ranked right, with the numbers to prove it.

A starter template lives in
[`examples/eval-cases.example.json`](https://github.com/GCrapuzzi/Talamus-Wiki/blob/main/examples/eval-cases.example.json).
