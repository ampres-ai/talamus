"""The Curator's health pass: every registered brain, one readable report —
zero LLM calls; missing brains degrade to a row, never a failure."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from talamus.config import TalamusConfig, save_config
from talamus.ingest import save_pending_capture
from talamus.paths import TalamusPaths
from talamus.registry import register_brain
from talamus.services.curator import curate_brains


def _make_brain(root: Path) -> TalamusPaths:
    paths = TalamusPaths(root)
    paths.ensure_directories()
    save_config(paths.config_path, replace(TalamusConfig.default(), llm_provider="claude-cli"))
    return paths


class CuratorTests(unittest.TestCase):
    def test_reports_every_registered_brain_with_attention_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            healthy = Path(tmp) / "healthy"
            waiting = Path(tmp) / "waiting"
            gone = Path(tmp) / "gone"
            for root in (healthy, waiting, gone):
                root.mkdir()
            _make_brain(healthy)
            paths = _make_brain(waiting)
            save_pending_capture(paths, "transcript", "diff", "usage limit")
            register_brain(healthy, name="healthy-brain")
            register_brain(waiting, name="waiting-brain")
            register_brain(gone, name="gone-brain")  # registered, then its config vanishes
            (gone / "talamus.json").unlink(missing_ok=True)

            result = curate_brains()

            self.assertTrue(result.success)
            rows = {row.name: row for row in (result.data or [])}
            self.assertIn("healthy-brain", rows)
            self.assertTrue(rows["healthy-brain"].reachable)
            self.assertEqual(1, rows["waiting-brain"].pending_captures)
            self.assertTrue(rows["waiting-brain"].attention)
            self.assertFalse(rows["gone-brain"].reachable)
            self.assertTrue(rows["gone-brain"].attention)
            self.assertIn("need attention", result.message)

    def test_fix_rebuilds_a_stale_cache_then_becomes_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "brain"
            root.mkdir()
            _make_brain(root)  # fresh brain: no cache manifest yet = stale
            register_brain(root, name="fixable-brain")

            first = curate_brains(fix=True)
            row = next(r for r in (first.data or []) if r.name == "fixable-brain")
            self.assertEqual(["reindexed stale cache"], row.fixed)
            self.assertTrue(row.cache_current)

            second = curate_brains(fix=True)
            row = next(r for r in (second.data or []) if r.name == "fixable-brain")
            self.assertEqual([], row.fixed)
            self.assertTrue(row.cache_current)


if __name__ == "__main__":
    unittest.main()
