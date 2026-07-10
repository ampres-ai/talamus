"""Captures survive engine failures: a failed session capture is saved locally
and retried until it succeeds, so a hit usage limit never loses a session.

The contract: `remember_session_safe` never raises on engine trouble — it
persists the transcript+diff under `.talamus/pending/` and audits the failure
in capture.log; `retry_pending_captures` replays every pending capture, keeps
the ones that fail again, and clears the ones that succeed."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from talamus.errors import EngineLimitReached
from talamus.ingest import (
    pending_captures,
    remember_session_safe,
    retry_pending_captures,
)
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.store import load_notes
from tests.support import FakeLLMProvider

TRANSCRIPT = (
    '{"role":"user","content":"come faccio X"}\n'
    '{"role":"assistant","content":"Si fa cosi perche serve Y"}'
)
DIFF = "diff --git a/x.py b/x.py\n+codice"

NOTE_JSON = json.dumps(
    [
        {
            "title": "Come fare X",
            "retrieval_text": "x",
            "summary": "Si fa cosi.",
            "supported_claims": ["x"],
            "confidence": 0.9,
        }
    ]
)


class LimitReachedProvider:
    """An engine whose usage limit is always exhausted."""

    def complete(self, prompt: str) -> str:
        raise EngineLimitReached("claude-cli", "usage limit reached — resets 3pm")


class CaptureRetryTests(unittest.TestCase):
    def _paths(self, tmp: str) -> TalamusPaths:
        paths = TalamusPaths(Path(tmp))
        paths.ensure_directories()
        return paths

    def test_engine_failure_saves_pending_and_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)

            result = remember_session_safe(
                paths, TRANSCRIPT, DIFF, StaticRouter(LimitReachedProvider())
            )

            self.assertTrue(result["failed"])
            self.assertEqual(0, result["notes_written"])
            pending = pending_captures(paths)
            self.assertEqual(1, len(pending))
            saved = json.loads(pending[0].read_text(encoding="utf-8"))
            self.assertEqual(TRANSCRIPT, saved["transcript"])
            self.assertEqual(DIFF, saved["diff"])
            self.assertIn("usage limit", saved["error"])
            log = (paths.logs / "capture.log").read_text(encoding="utf-8")
            self.assertIn("failed", log)
            self.assertIn("retry", log)

    def test_below_gate_sessions_do_not_become_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)

            result = remember_session_safe(
                paths, "ok grazie", "", StaticRouter(LimitReachedProvider())
            )

            self.assertTrue(result["skipped"])
            self.assertEqual([], pending_captures(paths))

    def test_retry_clears_pending_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            remember_session_safe(paths, TRANSCRIPT, DIFF, StaticRouter(LimitReachedProvider()))
            self.assertEqual(1, len(pending_captures(paths)))

            result = retry_pending_captures(paths, StaticRouter(FakeLLMProvider([NOTE_JSON])))

            self.assertEqual(1, result["retried"])
            self.assertEqual(0, result["remaining"])
            self.assertEqual([], pending_captures(paths))
            self.assertEqual(1, len(load_notes(paths)))
            log = (paths.logs / "capture.log").read_text(encoding="utf-8")
            self.assertIn("capture", log)

    def test_retry_keeps_pending_while_engine_still_failing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            remember_session_safe(paths, TRANSCRIPT, DIFF, StaticRouter(LimitReachedProvider()))

            result = retry_pending_captures(paths, StaticRouter(LimitReachedProvider()))

            self.assertEqual(0, result["retried"])
            self.assertEqual(1, result["remaining"])
            self.assertEqual(1, len(pending_captures(paths)))
            self.assertEqual(0, len(load_notes(paths)))

    def test_retry_with_nothing_pending_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)

            result = retry_pending_captures(paths, StaticRouter(FakeLLMProvider([])))

            self.assertEqual(0, result["retried"])
            self.assertEqual(0, result["remaining"])


if __name__ == "__main__":
    unittest.main()
