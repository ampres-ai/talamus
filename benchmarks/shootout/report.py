"""Write a shootout result as JSON (raw) + Markdown (readable), stamped with
provenance so any number is reconstructible."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path


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


def provenance(repo_root: Path, versions: dict[str, str]) -> dict:
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git": _git_head(repo_root),
        "versions": dict(versions),
    }


def _markdown(result: dict) -> str:
    lines = [
        "# Retrieval shootout",
        "",
        f"commit `{result['provenance']['git']}` · {result['provenance']['generated_at']} · "
        f"{result['n_docs']} docs · {result['n_queries']} queries · k={result['k']}",
        "",
        "| system | recall@k | MRR | hit | nDCG | p50 ms | ingest LLM calls |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, row in result["systems"].items():
        lines.append(
            f"| {name} | {row['recall_at_k']:.3f} | {row['mrr']:.3f} | {row['hit_rate']:.3f} "
            f"| {row['ndcg_at_k']:.3f} | {row['latency_ms_p50']:.1f} "
            f"| {row['ingest'].get('llm_calls', 0)} |"
        )
    return "\n".join(lines) + "\n"


def write_report(result: dict, versions: dict[str, str], out_dir: Path, tag: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {"provenance": provenance(Path.cwd(), versions), **result}
    stamp = time.strftime("%Y-%m-%d")
    json_path = out_dir / f"{stamp}-{tag}.json"
    md_path = out_dir / f"{stamp}-{tag}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(result), encoding="utf-8")
    return {"json": json_path, "md": md_path}
