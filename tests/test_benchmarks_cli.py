import io
import tempfile
import unittest
from contextlib import redirect_stdout

from benchmarks.run import main


class CliTests(unittest.TestCase):
    def test_ci_tier_runs_deterministic_systems_no_llm(self) -> None:
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(out):
            code = main(["--tier", "ci", "--out", tmp])
        self.assertEqual(code, 0)
        self.assertIn("talamus-search", out.getvalue())

    def test_shootout_without_yes_prints_estimate_and_stops(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--tier", "shootout"])
        self.assertEqual(code, 0)
        self.assertIn("--yes", out.getvalue())
