import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from talamus.services.integrations import (
    build_hook_snippet,
    inspect_integrations,
    install_capture_hook,
    install_mcp_config,
    install_mcp_config_cursor,
    install_mcp_for_agent,
)


class TalamusIntegrationServiceTests(unittest.TestCase):
    def test_install_mcp_config_preserves_other_servers_and_reports_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".mcp.json"
            config_path.write_text(
                json.dumps({"mcpServers": {"other": {"command": "other-mcp"}}}),
                encoding="utf-8",
            )

            result = install_mcp_config(root)
            status = inspect_integrations(root)

            data = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertTrue(result.success, result.message)
        self.assertIsNotNone(result.data)
        self.assertEqual(str(config_path), result.data.config_path)
        self.assertIn("other", data["mcpServers"])
        self.assertEqual("talamus-mcp", data["mcpServers"]["talamus"]["command"])
        self.assertEqual(["--root", str(root)], data["mcpServers"]["talamus"]["args"])
        self.assertTrue(status.success, status.message)
        self.assertIsNotNone(status.data)
        assert status.data is not None
        self.assertTrue(status.data.mcp_installed)

    def test_hook_snippet_contains_session_end_command_for_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = build_hook_snippet(root)

        self.assertTrue(result.success, result.message)
        snippet = result.data
        self.assertIsNotNone(snippet)
        assert snippet is not None
        self.assertIn(str(root), snippet.command)
        self.assertEqual(
            snippet.settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"],
            snippet.command,
        )

    def test_inspect_integrations_reports_absent_mcp_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("talamus.services.integrations.shutil.which", return_value=None):
                result = inspect_integrations(Path(tmp))

        self.assertTrue(result.success, result.message)
        report = result.data
        self.assertIsNotNone(report)
        assert report is not None
        self.assertFalse(report.mcp_installed)
        self.assertTrue(report.mcp_config_path.endswith(".mcp.json"))
        self.assertFalse(report.cursor_installed)
        self.assertFalse(report.codex_on_path)
        self.assertFalse(report.openclaw_on_path)
        self.assertFalse(report.hook_installed)

    def test_inspect_integrations_reports_cursor_codex_and_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_mcp_config_cursor(root)
            install_capture_hook(root)
            with mock.patch("talamus.services.integrations.shutil.which", return_value="codex"):
                result = inspect_integrations(root)

        self.assertTrue(result.success, result.message)
        report = result.data
        assert report is not None
        self.assertTrue(report.cursor_installed)
        self.assertTrue(report.codex_on_path)
        self.assertTrue(report.hook_installed)

    def test_install_mcp_for_agent_all_skips_a_missing_codex(self) -> None:
        # under auto/all a MISSING codex is a skip (reported, not fatal) — the
        # same contract as `talamus mcp install`; explicit codex must fail loudly
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch("talamus.services.integrations.shutil.which", return_value=None):
                all_result = install_mcp_for_agent(root, "all")
                explicit = install_mcp_for_agent(root, "codex")

        self.assertTrue(all_result.success, all_result.message)
        assert all_result.data is not None
        results = all_result.data["results"]
        self.assertTrue(results["claude"]["success"])
        self.assertTrue(results["cursor"]["success"])
        self.assertFalse(results["codex"]["success"])
        self.assertEqual("codex_not_found", results["codex"]["code"])
        self.assertFalse(results["openclaw"]["success"])
        self.assertEqual("openclaw_not_found", results["openclaw"]["code"])
        self.assertFalse(explicit.success)

    def test_install_mcp_for_agent_auto_detects_openclaw(self) -> None:
        calls: list[list[str]] = []

        def fake_which(command: str) -> str | None:
            return "C:/fake/openclaw.cmd" if command == "openclaw" else None

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return mock.Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("talamus.services.integrations.shutil.which", side_effect=fake_which):
                with mock.patch("talamus.services.integrations.subprocess.run", fake_run):
                    result = install_mcp_for_agent(tmp, "auto")

        self.assertTrue(result.success, result.message)
        assert result.data is not None
        self.assertIn("claude", result.data["results"])
        self.assertTrue(result.data["results"]["openclaw"]["success"])
        self.assertEqual(["C:/fake/openclaw.cmd", "mcp", "set", "talamus"], calls[0][:4])


if __name__ == "__main__":
    unittest.main()
