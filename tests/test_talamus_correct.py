import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from talamus.correct import apply_correction, verify_note
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import load_notes, rebuild_indexes, write_note
from talamus.timeline import note_history
from tests.support import FakeLLMProvider


def _note_with_source(tmp: str) -> CanonicalNote:
    (Path(tmp) / "norm").mkdir(parents=True, exist_ok=True)
    (Path(tmp) / "norm" / "x.md").write_text("La verita' dalla fonte.", encoding="utf-8")
    base = CanonicalNote.minimal(
        "X", sources=[SourceRef("norm/x.md", "norm/x.md", "loc", "sha256:x", ["c"])]
    )
    return dataclasses.replace(
        base,
        summary="riassunto sbagliato",
        body_sections={"definizione": "corpo sbagliato"},
        confidence=0.9,
    )


class CorrectTests(unittest.TestCase):
    def test_apply_correction_rewrites_and_keeps_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note_with_source(tmp))
            rebuild_indexes(paths)
            llm = FakeLLMProvider(
                [json.dumps({"ok": False, "summary": "corretto", "body": "corpo corretto"})]
            )

            changed = apply_correction(paths, "X", llm)

            self.assertTrue(changed)
            note = next(n for n in load_notes(paths) if n.title == "X")
            self.assertEqual("corretto", note.summary)
            self.assertGreaterEqual(len(note_history(paths, "X")), 2)

    def test_verify_reports_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note_with_source(tmp))
            rebuild_indexes(paths)

            result = verify_note(paths, "X", FakeLLMProvider([json.dumps({"ok": True})]))

            self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
