"""D7.2: the MCP server installs in one command across Claude Code, Cursor,
and Codex — the wow must survive the viewer trying it."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from talamus.cli import main
from talamus.services.integrations import (
    install_mcp_config_codex,
    install_mcp_config_cursor,
)


class CursorInstallTests(unittest.TestCase):
    def test_writes_cursor_mcp_json_with_talamus_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = install_mcp_config_cursor(tmp)
            data = json.loads((Path(tmp) / ".cursor" / "mcp.json").read_text(encoding="utf-8"))

        self.assertTrue(result.success, result.message)
        self.assertEqual("talamus-mcp", data["mcpServers"]["talamus"]["command"])
        self.assertEqual(["--root", tmp], data["mcpServers"]["talamus"]["args"])

    def test_merges_existing_cursor_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".cursor" / "mcp.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"mcpServers": {"other": {"command": "other-mcp"}}}),
                encoding="utf-8",
            )

            result = install_mcp_config_cursor(tmp)
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(result.success, result.message)
        self.assertIn("other", data["mcpServers"])
        self.assertIn("talamus", data["mcpServers"])


class CodexInstallTests(unittest.TestCase):
    def test_registers_globally_via_codex_cli(self) -> None:
        calls: list[list[str]] = []
        resolved = "C:/fake/npm/codex.cmd"  # subprocess needs the resolved shim path on Windows

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch("talamus.services.integrations.shutil.which", return_value=resolved):
            with mock.patch("talamus.services.integrations.subprocess.run", fake_run):
                result = install_mcp_config_codex()

        self.assertTrue(result.success, result.message)
        self.assertEqual([resolved, "mcp", "remove", "talamus"], calls[0])
        self.assertEqual([resolved, "mcp", "add", "talamus", "--", "talamus-mcp"], calls[1])

    def test_fails_actionably_when_codex_missing(self) -> None:
        with mock.patch("talamus.services.integrations.shutil.which", return_value=None):
            result = install_mcp_config_codex()

        self.assertFalse(result.success)
        self.assertIn("codex", result.message)

    def test_surfaces_codex_cli_failure(self) -> None:
        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["codex", "mcp", "add"]:
                return mock.Mock(returncode=1, stdout="", stderr="boom")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch("talamus.services.integrations.shutil.which", return_value="codex"):
            with mock.patch("talamus.services.integrations.subprocess.run", fake_run):
                result = install_mcp_config_codex()

        self.assertFalse(result.success)
        self.assertIn("boom", result.message)


class McpInstallCliTests(unittest.TestCase):
    def test_agent_all_writes_claude_and_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with (
                redirect_stdout(io.StringIO()),
                mock.patch("talamus.services.integrations.shutil.which", return_value=None),
            ):
                code = main(["mcp", "install", "--agent", "all", "--root", tmp])

            self.assertEqual(0, code)
            self.assertTrue((Path(tmp) / ".mcp.json").is_file())
            self.assertTrue((Path(tmp) / ".cursor" / "mcp.json").is_file())

    def test_auto_skips_cursor_without_cursor_dir_and_codex_off_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with (
                redirect_stdout(out),
                mock.patch("talamus.services.integrations.shutil.which", return_value=None),
            ):
                code = main(["mcp", "install", "--root", tmp])

            self.assertEqual(0, code)
            self.assertTrue((Path(tmp) / ".mcp.json").is_file())
            self.assertFalse((Path(tmp) / ".cursor").exists())

    def test_auto_includes_cursor_when_cursor_dir_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".cursor").mkdir()
            with (
                redirect_stdout(io.StringIO()),
                mock.patch("talamus.services.integrations.shutil.which", return_value=None),
            ):
                code = main(["mcp", "install", "--root", tmp])

            self.assertEqual(0, code)
            self.assertTrue((Path(tmp) / ".cursor" / "mcp.json").is_file())

    def test_agent_codex_without_codex_is_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with (
                redirect_stdout(io.StringIO()),
                redirect_stderr(err),
                mock.patch("talamus.services.integrations.shutil.which", return_value=None),
            ):
                code = main(["mcp", "install", "--agent", "codex", "--root", tmp])

            self.assertEqual(1, code)
            self.assertIn("codex", err.getvalue())


if __name__ == "__main__":
    unittest.main()
