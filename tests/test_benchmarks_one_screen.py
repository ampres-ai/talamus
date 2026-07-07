from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OneScreenBenchmarkTests(unittest.TestCase):
    def _run_one_screen(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "benchmarks/run.py", "--tier", "one-screen", *args],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_one_screen_renders_and_writes_temp_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            proc = self._run_one_screen("--out", str(out_dir))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            rendered = proc.stdout
            written = (out_dir / "one-screen.md").read_text(encoding="utf-8")
            self.assertIn("| claim | number | vs competitors | source artifact |", rendered)
            self.assertIn("multilingual-e5", rendered)
            self.assertEqual(written.strip(), rendered.strip())

    def test_source_artifact_cells_point_to_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            proc = self._run_one_screen("--out", td)

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            for line in proc.stdout.splitlines():
                if not line.startswith("| ") or line.startswith("| claim "):
                    continue
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) != 4 or cells[0].startswith("---"):
                    continue
                source_path = cells[3].split(" (", 1)[0]
                self.assertTrue((ROOT / source_path).exists(), source_path)

    def test_missing_artifact_fails_clearly(self) -> None:
        with (
            tempfile.TemporaryDirectory() as results_dir,
            tempfile.TemporaryDirectory() as out_dir,
        ):
            proc = self._run_one_screen("--results", results_dir, "--out", out_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("missing required artifact", proc.stderr.lower())
            self.assertIn("2026-06-17-shootout-book.json", proc.stderr)


if __name__ == "__main__":
    unittest.main()
