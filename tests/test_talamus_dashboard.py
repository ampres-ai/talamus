import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from talamus.cli import build_parser, main


class DashboardTests(unittest.TestCase):
    def _panel(self, cwd: str, home: str) -> str:
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}):
            previous = os.getcwd()
            os.chdir(cwd)
            try:
                with redirect_stdout(out):
                    code = main([])
            finally:
                os.chdir(previous)
        self.assertEqual(0, code)
        return out.getvalue()

    def test_dashboard_on_empty_dir_suggests_init(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
            text = self._panel(cwd, home)
            self.assertIn("Talamus", text)
            self.assertIn("Next", text)
            self.assertIn("talamus init", text)

    def test_dashboard_on_demo_brain_shows_state(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}):
                main(["init", "--root", cwd])
                main(["demo", "--root", cwd])
            text = self._panel(cwd, home)
            self.assertIn("Notes      3", text)
            self.assertIn("Indexes    fresh", text)
            self.assertIn("Ontology", text)
            # demo brain has no overview yet -> the dashboard suggests building it
            self.assertIn("talamus overview", text)

    def test_dashboard_lines_fit_100_columns(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}):
                main(["init", "--root", cwd])
                main(["demo", "--root", cwd])
            for line in self._panel(cwd, home).splitlines():
                self.assertLessEqual(len(line), 100, line)


class JsonCoverageTests(unittest.TestCase):
    def test_status_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main(["init", "--root", tmp])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["status", "--root", tmp, "--json"])
            self.assertEqual(0, code)
            self.assertTrue(json.loads(out.getvalue())["ok"])

    def test_status_json_includes_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main(["init", "--root", tmp])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["status", "--root", tmp, "--json"])

            payload = json.loads(out.getvalue())
            self.assertEqual(0, code)
            self.assertTrue(payload["ok"])
            self.assertIn("readiness", payload)
            readiness = payload["readiness"]
            self.assertEqual(str(Path(tmp).resolve()), readiness["root"])
            self.assertTrue(readiness["config_exists"])
            self.assertIsInstance(readiness["next_actions"], list)

    def test_status_json_preserves_brain_resolution_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                main(["init", "--root", tmp])
                out = io.StringIO()
                with redirect_stdout(out):
                    code = main(["status", "--brain", Path(tmp).name, "--json"])

            payload = json.loads(out.getvalue())
            self.assertEqual(0, code)
            readiness = payload["readiness"]
            self.assertEqual(str(Path(tmp).resolve()), readiness["root"])
            self.assertEqual("named", readiness["scope"])
            self.assertEqual("--brain", readiness["source"])

    def test_status_json_degrades_with_malformed_registry_before_root_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
            Path(home, "registry.json").write_text(
                json.dumps({"brains": [{"name": "broken"}]}), encoding="utf-8"
            )
            out = io.StringIO()
            previous = os.getcwd()
            try:
                os.chdir(cwd)
                with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                    with redirect_stdout(out):
                        code = main(["status", "--json"])
            finally:
                os.chdir(previous)

        payload = json.loads(out.getvalue())
        self.assertEqual(1, code)
        self.assertFalse(payload["ok"])
        readiness = payload["readiness"]
        self.assertEqual(str(Path(home, "default").resolve()), readiness["root"])
        self.assertFalse(readiness["config_exists"])

    def test_plain_flag_is_accepted_everywhere_common(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main(["init", "--root", tmp])
            self.assertEqual(0, main(["status", "--root", tmp, "--plain"]))
            self.assertEqual(0, main(["where", "--root", tmp, "--no-color"]))

    def test_plain_status_does_not_compute_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main(["init", "--root", tmp])
            with mock.patch("talamus.cli.lifecycle.inspect_readiness") as inspect:
                self.assertEqual(0, main(["status", "--root", tmp, "--plain"]))
            inspect.assert_not_called()


class HelpSnapshotTests(unittest.TestCase):
    def test_help_renders_under_100_columns_with_examples(self) -> None:
        parser = build_parser()
        text = parser.format_help()
        self.assertIn("examples:", text)
        for line in text.splitlines():
            self.assertLessEqual(len(line), 100, line)

    def test_help_output_is_utf8_safe(self) -> None:
        build_parser().format_help().encode("utf-8")  # must not raise


if __name__ == "__main__":
    unittest.main()
