"""Token-efficiency benchmark (dev-only).

Measures, on a real brain, the token cost of *targeted recall* versus *loading the
whole brain* — the core efficiency claim. Uses tiktoken (cl100k_base) as a proxy
for an LLM tokenizer. Not part of the package.

Setup:
    pip install -e ".[bench]"

Usage:
    python benchmarks/token_efficiency.py PATH_TO_BRAIN
"""

from __future__ import annotations

import sys
from pathlib import Path

import tiktoken

from talamus.paths import TalamusPaths
from talamus.recall import recall_context, search_notes
from talamus.store import load_notes

_ENC = tiktoken.get_encoding("cl100k_base")


def toks(text: str) -> int:
    return len(_ENC.encode(text))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    paths = TalamusPaths(Path(argv[0]).resolve())
    notes = load_notes(paths)
    md_files = sorted(paths.notes.glob("*.md"))
    if not notes or not md_files:
        print(f"No brain found at {paths.project_root} (run `talamus ingest` first).")
        return 1

    load_all = toks("\n\n".join(p.read_text(encoding="utf-8") for p in md_files))
    questions = [note.title for note in notes][:12]
    recall = [toks(recall_context(paths, q)) for q in questions]
    search = [
        toks("\n".join(f"- {r['title']}: {r['summary']}" for r in search_notes(paths, q)))
        for q in questions
    ]
    avg_recall = sum(recall) / len(recall)
    avg_search = sum(search) / len(search)

    recall_pct = (1 - avg_recall / load_all) * 100
    search_pct = (1 - avg_search / load_all) * 100
    print(f"notes in brain         : {len(notes)}")
    print(f"load-all (whole brain) : {load_all:>7} tok")
    print(f"recall (avg, targeted) : {avg_recall:>7.0f} tok   ({recall_pct:5.1f}% less)")
    print(f"search (avg, titles)   : {avg_search:>7.0f} tok   ({search_pct:5.1f}% less)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
