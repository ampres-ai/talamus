"""M2 (D6): the capture hook is consent-first — setup asks once, explains
exactly what is captured and where it goes, and writes the hook only on yes."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from talamus.cli import main
from talamus.services.integrations import build_hook_snippet, install_capture_hook


def _settings_path(root: str | Path) -> Path:
    return Path(root) / ".claude" / "settings.json"


def _session_end_commands(settings: dict) -> list[str]:
    commands: list[str] = []
    for entry in settings.get("hooks", {}).get("SessionEnd", []):
        for hook in entry.get("hooks", []):
            commands.append(hook.get("command", ""))
    return commands


class InstallCaptureHookServiceTests(unittest.TestCase):
    def test_install_writes_session_end_hook_to_claude_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = install_capture_hook(tmp)
            data = json.loads(_settings_path(tmp).read_text(encoding="utf-8"))

        self.assertTrue(result.success, result.message)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertTrue(result.data.installed)
        self.assertFalse(result.data.already_installed)
        commands = _session_end_commands(data)
        self.assertEqual(1, len(commands))
        self.assertIn("talamus hook-run", commands[0])

    def test_install_preserves_existing_settings_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _settings_path(tmp)
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "model": "opus",
                        "hooks": {
                            "PreToolUse": [{"hooks": [{"type": "command", "command": "x"}]}],
                            "SessionEnd": [{"hooks": [{"type": "command", "command": "other"}]}],
                        },
                    }
                ),
                encoding="utf-8",
            )

            first = install_capture_hook(tmp)
            second = install_capture_hook(tmp)
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(first.success, first.message)
        self.assertTrue(second.success, second.message)
        assert second.data is not None
        self.assertTrue(second.data.already_installed)
        self.assertEqual("opus", data["model"])
        self.assertEqual(1, len(data["hooks"]["PreToolUse"]))
        commands = _session_end_commands(data)
        self.assertEqual(1, len([c for c in commands if "talamus hook-run" in c]))
        self.assertIn("other", commands)

    def test_hook_command_quotes_root_against_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "my brain"
            root.mkdir()

            result = build_hook_snippet(root)

        assert result.data is not None
        self.assertIn(f'"{root}"', result.data.command)


class SetupConsentFlowTests(unittest.TestCase):
    def test_setup_capture_yes_installs_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                code = main(["setup", "--root", tmp, "--capture", "yes"])

            self.assertEqual(0, code)
            data = json.loads(_settings_path(tmp).read_text(encoding="utf-8"))
            self.assertTrue(any("talamus hook-run" in c for c in _session_end_commands(data)))

    def test_setup_capture_no_skips_hook_and_says_how_to_enable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["setup", "--root", tmp, "--capture", "no"])

            self.assertEqual(0, code)
            self.assertFalse(_settings_path(tmp).exists())
            self.assertIn("talamus hook --install", out.getvalue())

    def test_setup_ask_defaults_to_no_when_not_interactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_stdin = io.StringIO()  # isatty() is False
            with redirect_stdout(io.StringIO()), mock.patch("sys.stdin", fake_stdin):
                code = main(["setup", "--root", tmp])

            self.assertEqual(0, code)
            self.assertFalse(_settings_path(tmp).exists())

    def test_setup_ask_installs_on_interactive_yes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_stdin = mock.Mock()
            fake_stdin.isatty.return_value = True
            with (
                redirect_stdout(io.StringIO()),
                mock.patch("sys.stdin", fake_stdin),
                mock.patch("builtins.input", return_value="y"),
            ):
                code = main(["setup", "--root", tmp])

            self.assertEqual(0, code)
            data = json.loads(_settings_path(tmp).read_text(encoding="utf-8"))
            self.assertTrue(any("talamus hook-run" in c for c in _session_end_commands(data)))

    def test_consent_copy_names_the_data_the_destination_and_the_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                main(["setup", "--root", tmp, "--capture", "no"])

            copy = out.getvalue()
            self.assertIn("transcript", copy)
            self.assertIn("git diff", copy)
            self.assertIn("worth-remembering", copy)
            self.assertIn("capture.log", copy)
            self.assertIn(".claude/settings.json", copy.replace("\\", "/"))


class HookInstallCliTests(unittest.TestCase):
    def test_hook_install_flag_writes_the_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
                code = main(["hook", "--root", tmp, "--install"])

            self.assertEqual(0, code)
            data = json.loads(_settings_path(tmp).read_text(encoding="utf-8"))
            self.assertTrue(any("talamus hook-run" in c for c in _session_end_commands(data)))

    def test_hook_without_install_only_prints_snippet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
                code = main(["hook", "--root", tmp])

            self.assertEqual(0, code)
            self.assertFalse(_settings_path(tmp).exists())


if __name__ == "__main__":
    unittest.main()
