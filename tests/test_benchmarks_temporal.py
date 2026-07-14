"""Temporal-freshness benchmark plumbing: the two-version brain is built
correctly (supersedes recorded, timestamps backdated), the scorer counts
current/stale/change correctly, and artifacts are written — all with a fake
engine, zero LLM calls."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.temporal_eval import PAIRS, build_temporal_brain, run_temporal_eval

from talamus.ontology import load_ontology
from talamus.routing import StaticRouter


class TopicResponder:
    """Answers any prompt by finding which pair's question it carries and
    returning that pair's v2 marker — except for the pairs named in
    ``stale_pids``, which get a v1-only (stale) answer."""

    def __init__(self, stale_pids: set[str] | None = None) -> None:
        self.stale = stale_pids or set()

    def complete(self, prompt: str) -> str:
        for pair in PAIRS:
            if pair.question in prompt:
                if pair.pid in self.stale:
                    return f"You should use this: {pair.v1_marker}."
                return f"Current procedure: {pair.v2_marker} (it changed) [1]"
        return "no idea"


class TemporalBenchmarkTests(unittest.TestCase):
    def test_brain_has_both_versions_and_the_handover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_temporal_brain(Path(tmp))

            edges = [
                e for e in load_ontology(paths).get("edges", []) if e.get("type") == "supersedes"
            ]
            linked = sum(1 for p in PAIRS if p.linked)
            self.assertEqual(linked, len(edges))
            v1 = json.loads(
                (paths.notes_cache / f"{PAIRS[0].pid}-2025.json").read_text(encoding="utf-8")
            )
            self.assertTrue(v1["updated_at"].startswith("2025-"))

    def test_scoring_counts_current_stale_and_artifacts(self) -> None:
        stale_pid = next(p.pid for p in PAIRS if not p.linked)
        with (
            tempfile.TemporaryDirectory() as brain_dir,
            tempfile.TemporaryDirectory() as out_dir,
        ):
            result = run_temporal_eval(
                router=StaticRouter(TopicResponder({stale_pid})),
                out_dir=Path(out_dir),
                keep_dir=Path(brain_dir),
            )

            expected_hits = round((len(PAIRS) - 1) / len(PAIRS), 3)
            self.assertEqual(expected_hits, result["overall"]["current_hit"])
            self.assertAlmostEqual(
                1 / len([p for p in PAIRS if not p.linked]),
                result["unlinked_dated_only"]["stale"],
                places=3,
            )
            self.assertEqual(1.0, result["linked_supersedes"]["current_hit"])
            # the freshness pass mechanically dropped the old note on linked pairs
            self.assertEqual(1.0, result["linked_supersedes"]["old_excluded_from_context"])
            artifacts = list(Path(out_dir).glob("*-temporal.*"))
            self.assertEqual(2, len(artifacts))


if __name__ == "__main__":
    unittest.main()
