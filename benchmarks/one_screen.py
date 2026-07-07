"""The one-screen benchmark (B1, launch decision D7.3).

One reproducible, honest screen for the skeptical first commenter: what Talamus
wins, what it loses, and where every number comes from. This module MEASURES
NOTHING — it assembles the committed result artifacts under
``benchmarks/results/`` (plus the canonical ledger ``dev/STATE.md`` for the two
profiler headlines that have no JSON artifact) into one table. If an artifact
is missing, it fails loudly rather than rendering a partial story.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BOOK = "2026-06-17-shootout-book.json"
_SCIFACT = "2026-06-15-shootout-scifact.json"
_ASK = "2026-06-17-ask-eval.json"
_ASK_LOCAL = "2026-06-17-ask-eval-ollama.json"
_ABLATION = "2026-06-17-ask-ablation.json"
_SCALE = "2026-07-02-scale-100k.json"

REQUIRED = [_BOOK, _SCIFACT, _ASK, _ASK_LOCAL, _ABLATION, _SCALE]

_HEADER = "| claim | number | vs competitors | source artifact |"

_PARAGRAPH = """\
The honest read: on cross-language and vague queries (a real bilingual book
corpus) Talamus beats BM25 and a MiniLM vector DB with zero embedding
infrastructure, and its end-to-end judged answers lead every competitor while
refusing cleanly on questions the brain cannot answer. It does NOT win
everything: a strong multilingual dense model (multilingual-e5) ranks better
(nDCG/MRR) on that same corpus, and that row stays on this screen on purpose.
The trade Talamus offers is different: the semantic power comes from the LLM
you already have, so answers cost EUR 0 marginal, burn ~98% fewer tokens than
loading the corpus into context, and every answer cites sources you can open —
plus the time (as-of) and self-emerging-ontology moats no retrieval stack here
has. Reproduce it: every row's artifact is committed, with the command that
generated it in its sibling .md report."""


def _load(results_dir: Path, name: str) -> dict:
    return json.loads((results_dir / name).read_text(encoding="utf-8"))


def _fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def build_rows(results_dir: Path) -> list[tuple[str, str, str, str]]:
    """Every parsed number comes straight from its artifact — traceable by
    construction. The four STATE-sourced rows carry their ledger row instead."""
    book = _load(results_dir, _BOOK)["systems"]
    ask = _load(results_dir, _ASK)["systems"]
    ask_local = _load(results_dir, _ASK_LOCAL)["systems"]
    ablation = _load(results_dir, _ABLATION)
    scale = _load(results_dir, _SCALE)
    _load(results_dir, _SCIFACT)  # presence check; the post-fix numbers live in STATE (RS8)

    smart, bm25, minilm = book["talamus-smart"], book["bm25"], book["vectordb"]
    e5 = book["dense-multilingual"]
    ask_smart, ask_bm25, ask_minilm = ask["talamus-smart"], ask["bm25"], ask["vectordb"]
    at_10k = next(r for r in scale if r["n_notes"] == 10000)
    at_100k = next(r for r in scale if r["n_notes"] == 100000)

    results_rel = "benchmarks/results"
    return [
        (
            "Tokens per answer",
            "-97.7% vs loading the brain into context",
            "load-all grows linearly and hits the context wall",
            "dev/STATE.md (RS5 profiler row)",
        ),
        (
            "Answers cited & source-resolvable",
            "100%",
            "no competitor here has a provenance model",
            "dev/STATE.md (RS5 profiler row)",
        ),
        (
            "Marginal cost per answer",
            "EUR 0 (the LLM you already have)",
            "dense RAG pays embedding infrastructure per corpus",
            "dev/STATE.md (RS5 profiler row)",
        ),
        (
            "Cross-language + vague retrieval (book, hit@10)",
            f"talamus-smart {_fmt(smart['hit_rate'])} (recall {_fmt(smart['recall_at_k'])})",
            f"BM25 {_fmt(bm25['hit_rate'])} - MiniLM vector DB {_fmt(minilm['hit_rate'])}",
            f"{results_rel}/{_BOOK}",
        ),
        (
            "THE HONEST LOSS: strong dense ranking (book)",
            f"multilingual-e5 nDCG {_fmt(e5['ndcg_at_k'])} / MRR {_fmt(e5['mrr'])}",
            f"talamus-smart {_fmt(smart['ndcg_at_k'])} / {_fmt(smart['mrr'])} "
            "(we keep best hit/recall)",
            f"{results_rel}/{_BOOK}",
        ),
        (
            "English-only turf (SciFact, after the adaptive-trigram fix)",
            "talamus-search nDCG 0.664 / recall 0.797",
            "BM25 0.652 / 0.776 - MiniLM 0.645 / 0.783",
            f"dev/STATE.md (RS8 row; pre-fix baseline {results_rel}/{_SCIFACT})",
        ),
        (
            "Answer quality end-to-end (judged, book)",
            f"context hit {_fmt(ask_smart['context_hit'])} / "
            f"correctness {_fmt(ask_smart['answer_correctness'])}",
            f"BM25 {_fmt(ask_bm25['context_hit'])}/{_fmt(ask_bm25['answer_correctness'])} - "
            f"vector DB {_fmt(ask_minilm['context_hit'])}/"
            f"{_fmt(ask_minilm['answer_correctness'])}",
            f"{results_rel}/{_ASK}",
        ),
        (
            "The ontology improves ANSWERS (same brain, ON vs OFF)",
            f"ON: hit {_fmt(ablation['ontology_on']['context_hit'])} / "
            f"correct {_fmt(ablation['ontology_on']['answer_correctness'])}",
            f"OFF: {_fmt(ablation['ontology_off']['context_hit'])} / "
            f"{_fmt(ablation['ontology_off']['answer_correctness'])}",
            f"{results_rel}/{_ABLATION}",
        ),
        (
            "Fully local, EUR 0 (ollama gemma as generator AND judge)",
            f"correctness {_fmt(ask_local['talamus-search']['answer_correctness'])}",
            "0.857 with a cloud engine — a small, stated gap",
            f"{results_rel}/{_ASK_LOCAL}",
        ),
        (
            "Honest refusal on out-of-scope questions",
            f"{_fmt(ask_smart['honest_refusal'])}",
            "every competitor <= "
            + _fmt(max(ask_bm25["honest_refusal"], ask_minilm["honest_refusal"])),
            f"{results_rel}/{_ASK}",
        ),
        (
            "Search latency",
            f"p95 {at_10k['search']['p95_ms']:.1f} ms @10k - "
            f"p50 {at_100k['search']['p50_ms']:.1f} ms @100k",
            "no LLM call on the search path",
            f"{results_rel}/{_SCALE}",
        ),
    ]


def render(results_dir: Path) -> str:
    lines = [
        "# Talamus — the one-screen benchmark",
        "",
        _HEADER,
        "| --- | --- | --- | --- |",
    ]
    for claim, number, versus, source in build_rows(results_dir):
        lines.append(f"| {claim} | {number} | {versus} | {source} |")
    lines.extend(["", _PARAGRAPH, ""])
    return "\n".join(lines)


def run_one_screen(results_dir: Path, out_dir: Path) -> int:
    missing = [name for name in REQUIRED if not (results_dir / name).is_file()]
    if missing:
        for name in missing:
            print(f"missing required artifact: {results_dir / name}", file=sys.stderr, flush=True)
        return 2
    text = render(results_dir)
    print(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "one-screen.md").write_text(text, encoding="utf-8")
    return 0
