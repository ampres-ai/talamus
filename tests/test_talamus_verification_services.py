import json
import tempfile
import unittest
from pathlib import Path

from talamus.paths import TalamusPaths
from talamus.services.verification import (
    apply_note_correction,
    run_verification_batch,
    verify_single_note,
)
from talamus.store import load_notes, rebuild_indexes, write_note
from talamus.timeline import note_history
from tests.support import FakeLLMProvider
from tests.test_talamus_correct import _note_with_source
from tests.test_talamus_verify_batch import _brain


class TalamusVerificationServiceTests(unittest.TestCase):
    def test_batch_stale_report_makes_no_llm_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _brain(tmp)
            llm = FakeLLMProvider([])

            result = run_verification_batch(tmp, llm, only_stale=True)

        self.assertTrue(result.success, result.message)
        self.assertEqual("verification_batch_completed", result.code)
        self.assertEqual([], llm.prompts)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(2, result.data.stale)
        self.assertEqual(0, result.data.checked)

    def test_verify_single_note_returns_typed_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note_with_source(tmp))
            rebuild_indexes(paths)

            result = verify_single_note(tmp, "X", FakeLLMProvider([json.dumps({"ok": True})]))

        self.assertTrue(result.success, result.message)
        self.assertEqual("verification_note_checked", result.code)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertTrue(result.data.found)
        self.assertTrue(result.data.checked)
        self.assertTrue(result.data.ok)

    def test_apply_note_correction_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note_with_source(tmp))
            rebuild_indexes(paths)
            llm = FakeLLMProvider(
                [json.dumps({"ok": False, "summary": "corretto", "body": "corpo corretto"})]
            )

            result = apply_note_correction(tmp, "X", llm)

            note = next(note for note in load_notes(paths) if note.title == "X")
            versions = note_history(paths, "X")

        self.assertTrue(result.success, result.message)
        self.assertEqual("verification_correction_applied", result.code)
        self.assertEqual("corretto", note.summary)
        self.assertGreaterEqual(len(versions), 2)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertTrue(result.data.corrected)


if __name__ == "__main__":
    unittest.main()
