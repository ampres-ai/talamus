"""Measurement baseline — retrieval quality, latency, and cost curves.

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
    "search/recall/read/history/neighbors": {"calls": 0, "note": "local indexes only"},
    "ask (normal path)": {"calls": 2, "note": "overview routing + answer"},
    "ask (expansion fallback)": {"calls": 3, "note": "routing + expansion + answer"},
    "ingest (per file)": {"calls": 1, "note": "1 extraction per file"},
    "overview --rebuild": {"calls": 1, "note": "naming / domain assignment"},
    "verify (per note)": {"calls": 1, "note": "note-vs-source comparison"},
    "consolidate (detection)": {"calls": 1, "note": "duplicate detection"},
    "remember (per session)": {"calls": 1, "note": "extraction from the session"},
}

_ROUTE_PROMPT_OVERHEAD = (
    "Given the MAP of domains (name: description) and a QUESTION, return ONLY the "
    "names of the relevant domains, comma-separated. No other words."
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
    targeted = [f"concept{i:05d} memory graph" for i in range(0, n, step)][:how_many]
    return [*targeted, "retrieval index ontology domain"]


def measure_latency(paths: TalamusPaths, n: int) -> dict:
    """Production search (persistent index, M4) vs the legacy in-memory full scan."""
    queries = _synthetic_queries(n)
    search: list[float] = []
    for query in queries:
        start = time.perf_counter()
        search_notes(paths, query)
        search.append((time.perf_counter() - start) * 1000)
    graph = load_graph(paths.graph_file)
    index = BM25Index.load(paths.index_file)
    legacy: list[float] = []
    for query in queries * 3:
        start = time.perf_counter()
        index.search(query, limit=10)
        query_graph_scored(graph, query, limit=10)
        legacy.append((time.perf_counter() - start) * 1000)
    return {"n_notes": n, "search": percentiles(search), "legacy_scan": percentiles(legacy)}


def run_scale(sizes: list[int] | None = None) -> list[dict]:
    """Scale benchmark (F3.4): latency + index size at growing synthetic corpora."""
    from talamus.indexes import backend_info

    rows: list[dict] = []
    for n in sizes or [100, 1000, 10000]:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            build_synthetic_corpus(paths, n, render=False)
            row = measure_latency(paths, n)
            row["index"] = backend_info(paths)
            rows.append(row)
    return rows


def routing_prompt_tokens(n_notes: int, notes_per_domain: int = 10) -> dict:
    """Estimated token size of the single-level overview routing prompt at N notes."""
    n_domains = max(1, n_notes // notes_per_domain)
    domain_map = "\n".join(
        f"- Example domain {i:04d}: one-line description of the domain's content"
        for i in range(n_domains)
    )
    prompt = f"{_ROUTE_PROMPT_OVERHEAD}\n\nMAP:\n{domain_map}\n\nQUESTION: example question"
    return {"n_notes": n_notes, "n_domains": n_domains, "prompt_tokens": estimate_tokens(prompt)}


def routing_prompt_tokens_tree(
    n_notes: int, notes_per_domain: int = 10, domains_per_area: int = 10
) -> dict:
    """Two-level routing: areas prompt + one area's domains prompt.

    Flat routing lists every domain (O(N)); the tree lists ~N/100 areas plus ~10
    domains — the sum stays bounded as the brain grows."""
    n_domains = max(1, n_notes // notes_per_domain)
    n_areas = max(1, n_domains // domains_per_area)
    line = "- area-{i:04d} | Example area: one-line description"
    areas_map = "\n".join(line.format(i=i) for i in range(n_areas))
    level_one = f"{_ROUTE_PROMPT_OVERHEAD}\n\nMAP:\n{areas_map}\n\nQUESTION: example"
    domains_map = "\n".join(
        f"- dom-{i:04d} | Example domain: one-line description"
        for i in range(min(domains_per_area, n_domains))
    )
    level_two = f"{_ROUTE_PROMPT_OVERHEAD}\n\nMAP:\n{domains_map}\n\nQUESTION: example"
    return {
        "n_notes": n_notes,
        "n_areas": n_areas,
        "prompt_tokens": estimate_tokens(level_one) + estimate_tokens(level_two),
    }


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

    result["latency"] = run_scale(sizes)
    result["routing_tokens"] = [routing_prompt_tokens(n) for n in [100, 1000, 10000, 100000]]
    result["llm_call_ledger"] = LLM_CALL_LEDGER
    return result


def _eval_section(eval_data: dict) -> list[str]:
    lines = [
        "## Retrieval — real eval-set",
        "",
        f"- cases: **{eval_data['n_cases']}** ({eval_data['n_negative']} negatives)",
        f"- recall@{eval_data['k']}: **{eval_data['recall_at_k']}**",
        f"- precision@{eval_data['k']}: **{eval_data['precision_at_k']}**",
        f"- MRR: **{eval_data['mrr']}**",
        f"- hit-rate: **{eval_data['hit_rate']}**",
        f"- negative rejection (retrieval-level): **{eval_data['negative_rejection']}**",
        "",
        "| category | n | recall@k | MRR | hit-rate |",
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
        "# Baseline M0 — retrieval measurements (pre-final-architecture)",
        "",
        f"Generated: {result['generated_at']} · commit `{result['git']}` · real corpus: "
        f"{result['docs_corpus_notes']} notes from the repo docs (deterministic, no LLM)",
        "",
        *_eval_section(result["eval"]),
        "",
        "## Retrieval latency (synthetic)",
        "",
        "search = production `search_notes` (persistent index, M4) · legacy = the old",
        "full in-memory scan (BM25+graph), kept as a comparison.",
        "",
        "| notes | search p50 (ms) | search p95 (ms) | legacy p50 (ms) | legacy p95 (ms) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in result["latency"]:
        lines.append(
            f"| {row['n_notes']} | {row['search']['p50_ms']} | {row['search']['p95_ms']}"
            f" | {row['legacy_scan']['p50_ms']} | {row['legacy_scan']['p95_ms']} |"
        )
    lines += [
        "",
        "## Overview routing token curve (single-level, ~1 domain/10 notes)",
        "",
        "| notes | domains | routing prompt tokens |",
        "| --- | --- | --- |",
    ]
    for row in result["routing_tokens"]:
        lines.append(f"| {row['n_notes']} | {row['n_domains']} | {row['prompt_tokens']} |")
    lines += [
        "",
        "## LLM call ledger per workflow (current architecture)",
        "",
        "| workflow | calls | note |",
        "| --- | --- | --- |",
    ]
    for name, info in result["llm_call_ledger"].items():
        lines.append(f"| {name} | {info['calls']} | {info['note']} |")
    lines += [
        "",
        "## Honest notes",
        "",
        "- The *temporal* cases query historical content present in the docs: true as-of",
        "  semantics arrive with M6; here they only measure lexical/graph retrieval.",
        "- Negative rejection at the retrieval level is expected to be weak: without score",
        "  thresholds the search always returns something if a term matches (M4).",
        "- *Cold* latency dominates because `search_notes` reloads notes and indexes on",
        "  every call: it is the O(N) bottleneck that M4 (persistent indexes) removes.",
        "- The web workbench is verified by its service/API tests; runtime browser",
        "  verification is handled outside this baseline benchmark.",
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
    print(f"baseline written to {out}/{stamp}-m0-baseline.md")
    print(f"  eval: recall@5={result['eval']['recall_at_k']} mrr={result['eval']['mrr']}")
    for row in result["latency"]:
        print(f"  latency {row['n_notes']} notes: search p95 {row['search']['p95_ms']}ms")
    return result
