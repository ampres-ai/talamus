"""Ontology ON/OFF ablation on the REAL ask path.

ON  = answer_question as shipped: routes via the hierarchical overview, whose
      domains are built by union-find over the emergent ontology edges.
OFF = the same brain with the overview removed → ask falls back to the plain
      persistent-index path (no ontology-derived domain routing).

Same generation code both ways; the only variable is the ontology/routing
layer. This is the honest test of whether the emergent ontology pays off in
ANSWER quality, not just in navigation/routing cost."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from benchmarks.ask_eval.judges import correctness_verdict, faithfulness_verdict
from benchmarks.shootout.corpora.judged import JudgedCorpus
from talamus.naming import note_filename
from talamus.paths import TalamusPaths


def _strip_overview(brain: str) -> str:
    """Copy the brain to a temp dir with the overview removed (ontology routing off)."""
    dst = tempfile.mkdtemp(prefix="ablate-off-")
    shutil.copytree(brain, dst, dirs_exist_ok=True)
    cache = TalamusPaths(Path(dst)).cache
    for name in ("overview.json", "overview-tree.json"):
        (cache / name).unlink(missing_ok=True)
    return dst


def _context_hit(items_read: list[str], relevant_titles: set[str]) -> bool:
    wanted = {note_filename(t) for t in relevant_titles}
    return any(any(p.endswith(w) for w in wanted) for p in items_read)


def _run(paths: TalamusPaths, corpus: JudgedCorpus, ask_llm, judge_llm) -> dict:
    from talamus.ask import answer_question
    from talamus.routing import StaticRouter

    router = StaticRouter(ask_llm)
    text_by_id = {doc_id: text for doc_id, _t, text in corpus.docs}
    faithful = correct = hit = 0
    n = 0
    routes: dict[str, int] = {}
    for qid, question in corpus.queries.items():
        relevant = set(corpus.qrels.get(qid, {}))
        trace: dict = {}
        answer = answer_question(paths, question, router, trace=trace)
        routes[trace.get("route", "?")] = routes.get(trace.get("route", "?"), 0) + 1
        if _context_hit(trace.get("items_read", []), relevant):
            hit += 1
        # Faithfulness must judge against what the ask ACTUALLY read, not the gold
        # docs (known artifact: ontology_on reads richer context and was wrongly
        # penalised as 'less grounded in gold'). Fall back to gold if no trace.
        read = [Path(p) for p in trace.get("items_read", [])]
        actual_ctx = "\n\n".join(p.read_text("utf-8") for p in read if p.is_file())
        reference = "\n".join(text_by_id[i] for i in relevant if i in text_by_id)
        if faithfulness_verdict(answer, actual_ctx or reference, judge_llm):
            faithful += 1
        grade = correctness_verdict(answer, question, reference, judge_llm)
        correct += {"correct": 1.0, "partial": 0.5, "wrong": 0.0}[grade]
        n += 1
    return {
        "n": n,
        "context_hit": round(hit / n, 3) if n else 0.0,
        "faithfulness": round(faithful / n, 3) if n else 0.0,
        "answer_correctness": round(correct / n, 3) if n else 0.0,
        "routes": routes,
    }


def evaluate_ontology_ablation(brain: str, corpus: JudgedCorpus, ask_llm, judge_llm) -> dict:
    on = _run(TalamusPaths(Path(brain)), corpus, ask_llm, judge_llm)
    off_dir = _strip_overview(brain)
    try:
        off = _run(TalamusPaths(Path(off_dir)), corpus, ask_llm, judge_llm)
    finally:
        shutil.rmtree(off_dir, ignore_errors=True)
    return {"ontology_on": on, "ontology_off": off}
