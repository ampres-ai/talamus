"""Measurement baseline (PRD M0) — retrieval quality, latency, and cost curves.

Everything here is deterministic and LLM-free. ``run_baseline`` builds the real
docs corpus, runs the real eval-set, measures retrieval latency on synthetic
corpora at increasing sizes (cold = the true current cost including index/note
loading; warm = the in-memory algorithmic cost), models the overview-routing
token curve, and writes JSON + Markdown artifacts under ``docs/benchmarks/``.

Run with:  python -c "from talamus.bench import main; main()"
"""

from __future__ import annotations

import json
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from talamus.budget import estimate_tokens
from talamus.corpus import build_docs_corpus, build_synthetic_corpus
from talamus.eval import evaluate, load_cases, search_retriever
from talamus.graph import load_graph, query_graph_scored
from talamus.paths import TalamusPaths
from talamus.recall import search_notes
from talamus.search import BM25Index

# Static ledger: LLM calls per workflow in the current architecture.
LLM_CALL_LEDGER: dict[str, dict] = {
    "search/recall/read/history/neighbors": {"calls": 0, "note": "solo indici locali"},
    "ask (percorso normale)": {"calls": 2, "note": "routing overview + risposta"},
    "ask (fallback espansione)": {"calls": 3, "note": "routing + espansione + risposta"},
    "ingest (per file)": {"calls": 1, "note": "1 estrazione per file"},
    "overview --rebuild": {"calls": 1, "note": "naming/assegnazione domini"},
    "verify (per nota)": {"calls": 1, "note": "confronto nota-fonte"},
    "consolidate (rilevazione)": {"calls": 1, "note": "rilevazione duplicati"},
    "remember (per sessione)": {"calls": 1, "note": "estrazione dalla sessione"},
}

_ROUTE_PROMPT_OVERHEAD = (
    "Data la MAPPA dei domini (nome: descrizione) e una DOMANDA, restituisci "
    "SOLO i nomi dei domini pertinenti, separati da virgola. Nessun'altra parola."
)


def percentiles(samples_ms: list[float]) -> dict:
    ordered = sorted(samples_ms)
    if not ordered:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "n_samples": 0}
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    return {"p50_ms": round(p50, 2), "p95_ms": round(p95, 2), "n_samples": len(ordered)}


def _synthetic_queries(n: int, how_many: int = 5) -> list[str]:
    step = max(1, n // how_many)
    targeted = [f"concetto{i:05d} memoria grafo" for i in range(0, n, step)][:how_many]
    return [*targeted, "recupero indice ontologia dominio"]


def measure_latency(paths: TalamusPaths, n: int) -> dict:
    """Cold (full search_notes incl. loads) vs warm (in-memory BM25+graph) latency."""
    queries = _synthetic_queries(n)
    cold: list[float] = []
    for query in queries:
        start = time.perf_counter()
        search_notes(paths, query)
        cold.append((time.perf_counter() - start) * 1000)
    graph = load_graph(paths.graph_file)
    index = BM25Index.load(paths.index_file)
    warm: list[float] = []
    for query in queries * 3:
        start = time.perf_counter()
        index.search(query, limit=10)
        query_graph_scored(graph, query, limit=10)
        warm.append((time.perf_counter() - start) * 1000)
    return {"n_notes": n, "cold": percentiles(cold), "warm": percentiles(warm)}


def routing_prompt_tokens(n_notes: int, notes_per_domain: int = 10) -> dict:
    """Estimated token size of the single-level overview routing prompt at N notes."""
    n_domains = max(1, n_notes // notes_per_domain)
    domain_map = "\n".join(
        f"- Dominio di esempio {i:04d}: descrizione di una riga del contenuto del dominio"
        for i in range(n_domains)
    )
    prompt = f"{_ROUTE_PROMPT_OVERHEAD}\n\nMAPPA:\n{domain_map}\n\nDOMANDA: domanda di esempio"
    return {"n_notes": n_notes, "n_domains": n_domains, "prompt_tokens": estimate_tokens(prompt)}


def _git_head(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def run_baseline(
    repo_root: Path,
    cases_file: Path,
    sizes: list[int] | None = None,
    k: int = 5,
) -> dict:
    sizes = sizes or [100, 1000, 10000]
    result: dict = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "git": _git_head(repo_root)}

    with tempfile.TemporaryDirectory() as tmp:
        paths = TalamusPaths(Path(tmp))
        titles = build_docs_corpus(paths, repo_root)
        cases = load_cases(cases_file)
        report = evaluate(cases, search_retriever(paths), k=k)
        result["docs_corpus_notes"] = len(titles)
        result["eval"] = report.to_dict()

    latency: list[dict] = []
    for n in sizes:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            build_synthetic_corpus(paths, n, render=False)
            latency.append(measure_latency(paths, n))
    result["latency"] = latency
    result["routing_tokens"] = [routing_prompt_tokens(n) for n in [100, 1000, 10000, 100000]]
    result["llm_call_ledger"] = LLM_CALL_LEDGER
    return result


def _eval_section(eval_data: dict) -> list[str]:
    lines = [
        "## Recupero — eval-set reale",
        "",
        f"- casi: **{eval_data['n_cases']}** (di cui {eval_data['n_negative']} negativi)",
        f"- recall@{eval_data['k']}: **{eval_data['recall_at_k']}**",
        f"- precision@{eval_data['k']}: **{eval_data['precision_at_k']}**",
        f"- MRR: **{eval_data['mrr']}**",
        f"- hit-rate: **{eval_data['hit_rate']}**",
        f"- rifiuto dei negativi (retrieval-level): **{eval_data['negative_rejection']}**",
        "",
        "| categoria | n | recall@k | MRR | hit-rate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, stats in sorted(eval_data["categories"].items()):
        lines.append(
            f"| {name} | {stats['n']} | {stats['recall_at_k']} | {stats['mrr']}"
            f" | {stats['hit_rate']} |"
        )
    return lines


def format_report(result: dict) -> str:
    lines = [
        "# Baseline M0 — misure del recupero (pre-architettura finale)",
        "",
        f"Generato: {result['generated_at']} · commit `{result['git']}` · corpus reale: "
        f"{result['docs_corpus_notes']} note dai doc del repo (deterministico, no LLM)",
        "",
        *_eval_section(result["eval"]),
        "",
        "## Latenza del recupero (sintetico, attuale architettura O(N))",
        "",
        "cold = `search_notes` completa (incl. caricamento note+indici da disco, il costo vero",
        "di oggi) · warm = solo BM25+grafo in memoria (costo algoritmico).",
        "",
        "| note | cold p50 (ms) | cold p95 (ms) | warm p50 (ms) | warm p95 (ms) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in result["latency"]:
        lines.append(
            f"| {row['n_notes']} | {row['cold']['p50_ms']} | {row['cold']['p95_ms']}"
            f" | {row['warm']['p50_ms']} | {row['warm']['p95_ms']} |"
        )
    lines += [
        "",
        "## Curva token del routing overview (single-level, ~1 dominio/10 note)",
        "",
        "| note | domini | token prompt routing |",
        "| --- | --- | --- |",
    ]
    for row in result["routing_tokens"]:
        lines.append(f"| {row['n_notes']} | {row['n_domains']} | {row['prompt_tokens']} |")
    lines += [
        "",
        "## Ledger chiamate LLM per workflow (architettura attuale)",
        "",
        "| workflow | chiamate | nota |",
        "| --- | --- | --- |",
    ]
    for name, info in result["llm_call_ledger"].items():
        lines.append(f"| {name} | {info['calls']} | {info['note']} |")
    lines += [
        "",
        "## Note oneste",
        "",
        "- I casi *temporal* interrogano contenuto storico presente nei doc: la semantica",
        "  as-of vera arriva con M6; qui misurano solo il recupero lessicale/grafo.",
        "- Il rifiuto dei negativi a livello retrieval è atteso debole: senza soglie di",
        "  punteggio la ricerca restituisce sempre qualcosa se un termine combacia (M4).",
        "- La latenza *cold* domina perché `search_notes` ricarica note e indici a ogni",
        "  chiamata: è il collo di bottiglia O(N) che M4 (indici persistiti) elimina.",
        "- La UI è type-checked contro Flet ma non verificata a runtime in questa sessione",
        "  (richiede display); la verifica runtime resta in sospeso (M9 aggiunge web test mode).",
    ]
    return "\n".join(lines) + "\n"


def main(out_dir: str = "docs/benchmarks", sizes: list[int] | None = None) -> dict:
    repo_root = Path.cwd()
    cases_file = repo_root / "examples" / "eval-cases-real.json"
    result = run_baseline(repo_root, cases_file, sizes=sizes)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d")
    (out / f"{stamp}-m0-baseline.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / f"{stamp}-m0-baseline.md").write_text(format_report(result), encoding="utf-8")
    print(f"baseline scritta in {out}/{stamp}-m0-baseline.md")
    print(f"  eval: recall@5={result['eval']['recall_at_k']} mrr={result['eval']['mrr']}")
    for row in result["latency"]:
        print(f"  latenza {row['n_notes']} note: cold p95 {row['cold']['p95_ms']}ms")
    return result
