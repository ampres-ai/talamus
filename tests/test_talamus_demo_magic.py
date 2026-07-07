from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


def _load_run_magic():
    script = Path(__file__).resolve().parents[1] / "scripts" / "demo" / "run_magic.py"
    spec = importlib.util.spec_from_file_location("talamus_demo_run_magic", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _session_end_commands(settings: dict) -> list[str]:
    commands: list[str] = []
    for entry in settings.get("hooks", {}).get("SessionEnd", []):
        for hook in entry.get("hooks", []):
            commands.append(str(hook.get("command", "")))
    return commands


class MagicDemoHarnessTests(unittest.TestCase):
    def _new_demo_root(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="talamus-demo-test-"))
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def test_fake_mode_runs_the_full_memory_arc(self) -> None:
        run_magic = _load_run_magic()
        with mock.patch.dict(os.environ, {}, clear=False):
            tmp = str(self._new_demo_root())
            out = io.StringIO()
            with redirect_stdout(out):
                code = run_magic.main(["--fake", "--dir", tmp, "--keep"])

            root = Path(tmp)
            settings = json.loads((root / ".claude" / "settings.json").read_text("utf-8"))
            commands = _session_end_commands(settings)
            capture_log = (root / ".talamus" / "logs" / "capture.log").read_text("utf-8")
            notes = list((root / "notes").glob("*.md"))
            output = out.getvalue()

        self.assertEqual(0, code)
        self.assertTrue(any("talamus hook-run" in command for command in commands))
        self.assertIn("capture", capture_log)
        self.assertTrue(notes)
        self.assertTrue(any("session-" in note.read_text("utf-8") for note in notes))
        self.assertIn("SQLite FTS5 Porter Search Decision", output)

    def test_fake_mode_reports_below_gate_transcript_honestly(self) -> None:
        run_magic = _load_run_magic()
        with mock.patch.dict(os.environ, {}, clear=False):
            tmp = str(self._new_demo_root())
            short = Path(tmp) / "short-transcript.jsonl"
            short.write_text('{"role":"user","content":"ok"}\n', encoding="utf-8")
            out = io.StringIO()

            with redirect_stdout(out):
                code = run_magic.main(
                    ["--fake", "--dir", tmp, "--keep", "--transcript-file", str(short)]
                )

            output = out.getvalue()

        self.assertNotEqual(0, code)
        self.assertIn("below worth-remembering gate", output)
        self.assertIn("No note was born", output)


if __name__ == "__main__":
    unittest.main()
