import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from talamus.adapters.llm import (
    CodexCliProvider,
    GeminiCliProvider,
    build_provider,
    save_credential,
)


class CliAdapterTests(unittest.TestCase):
    def test_codex_uses_exec_with_stdin_prompt(self) -> None:
        calls: list[tuple[list[str], str]] = []

        def runner(args: list[str], prompt: str) -> str:
            calls.append((args, prompt))
            return "risposta"

        provider = CodexCliProvider(runner=runner)
        self.assertEqual(provider.complete("domanda lunga" * 100), "risposta")
        args, prompt = calls[0]
        self.assertEqual(args, ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "-"])
        self.assertIn("domanda lunga", prompt)  # prompt on stdin, not argv

    def test_gemini_headless_with_stdin_prompt(self) -> None:
        calls: list[tuple[list[str], str]] = []

        def runner(args: list[str], prompt: str) -> str:
            calls.append((args, prompt))
            return "ok"

        GeminiCliProvider(runner=runner).complete("ciao")
        args, prompt = calls[0]
        self.assertEqual(args, ["gemini", "--skip-trust", "--approval-mode", "plan", "-p", ""])
        self.assertEqual(prompt, "ciao")

    def test_model_passthrough_for_bulk_ingest(self) -> None:
        """config llm_model reaches the CLI via -m (fast models for big books)."""
        calls: list[list[str]] = []

        def runner(args: list[str], prompt: str) -> str:
            calls.append(args)
            return "ok"

        CodexCliProvider(model="gpt-5.4-mini", runner=runner).complete("x")
        GeminiCliProvider(model="gemini-2.5-flash", runner=runner).complete("x")
        self.assertIn("-m", calls[0])
        self.assertEqual(calls[0][calls[0].index("-m") + 1], "gpt-5.4-mini")
        self.assertEqual(calls[0][-1], "-")  # stdin marker stays last
        self.assertIn("-m", calls[1])
        self.assertEqual(calls[1][calls[1].index("-m") + 1], "gemini-2.5-flash")
        self.assertEqual(calls[1][-2:], ["-p", ""])  # headless mode stays intact

    def test_build_provider_knows_the_new_engines(self) -> None:
        self.assertIsInstance(build_provider("codex-cli"), CodexCliProvider)
        self.assertIsInstance(build_provider("gemini-cli"), GeminiCliProvider)
        self.assertIsInstance(build_provider("codex"), CodexCliProvider)


class CredentialStoreTests(unittest.TestCase):
    def test_windows_acl_policy_ignores_only_safe_bookkeeping_flags(self) -> None:
        from talamus.credentials import _windows_dacl_is_owner_only_sddl

        sid = "S-1-5-21-1-2-3-1001"
        self.assertTrue(_windows_dacl_is_owner_only_sddl(f"D:P(A;;FA;;;{sid})", sid))
        self.assertTrue(_windows_dacl_is_owner_only_sddl(f"D:PAI(A;;FA;;;{sid})", sid))
        self.assertTrue(_windows_dacl_is_owner_only_sddl(f"D:AIP(A;;0x001f01ff;;;{sid})", sid))
        self.assertFalse(_windows_dacl_is_owner_only_sddl(f"D:AI(A;;FA;;;{sid})", sid))
        self.assertFalse(_windows_dacl_is_owner_only_sddl(f"D:P(A;CI;FA;;;{sid})", sid))
        self.assertFalse(
            _windows_dacl_is_owner_only_sddl(f"D:P(A;;FA;;;{sid})(A;;FR;;;S-1-1-0)", sid)
        )

    def test_save_and_read_credential_roundtrip(self) -> None:
        from talamus.adapters.llm import _stored_credential

        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}):
                self.assertEqual(_stored_credential("anthropic_api_key"), "")
                save_credential("anthropic_api_key", "sk-test-123")
                self.assertEqual(_stored_credential("anthropic_api_key"), "sk-test-123")
                data = json.loads((Path(home) / "credentials.json").read_text(encoding="utf-8"))
                self.assertEqual(data["anthropic_api_key"], "sk-test-123")

                from talamus.credentials import credential_file_is_owner_only

                self.assertTrue(credential_file_is_owner_only(Path(home) / "credentials.json"))

    def test_save_tightens_existing_file_and_preserves_values(self) -> None:
        from talamus.credentials import credential_file_is_owner_only

        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "credentials.json"
            path.write_text(json.dumps({"existing": "keep-me"}), encoding="utf-8")
            if os.name != "nt":
                path.chmod(0o666)
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}):
                save_credential("anthropic_api_key", "sk-new")
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"existing": "keep-me", "anthropic_api_key": "sk-new"},
            )
            self.assertTrue(credential_file_is_owner_only(path))

    def test_permission_failure_writes_no_credential(self) -> None:
        from talamus.errors import CredentialStoreError

        with tempfile.TemporaryDirectory() as home:
            with (
                mock.patch.dict(os.environ, {"TALAMUS_HOME": home}),
                mock.patch(
                    "talamus.credentials._harden_before_write",
                    side_effect=OSError("permission denied"),
                ),
            ):
                with self.assertRaisesRegex(CredentialStoreError, "not saved"):
                    save_credential("anthropic_api_key", "sk-must-not-land")
            self.assertFalse((Path(home) / "credentials.json").exists())
            self.assertEqual(list(Path(home).glob(".credentials.json.*.tmp")), [])

    def test_permission_failure_leaves_existing_credentials_unchanged(self) -> None:
        from talamus.errors import CredentialStoreError

        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "credentials.json"
            original = json.dumps({"existing": "keep-me"})
            path.write_text(original, encoding="utf-8")
            with (
                mock.patch.dict(os.environ, {"TALAMUS_HOME": home}),
                mock.patch(
                    "talamus.credentials._harden_before_write",
                    side_effect=OSError("permission denied"),
                ),
            ):
                with self.assertRaises(CredentialStoreError):
                    save_credential("anthropic_api_key", "sk-must-not-land")
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(list(Path(home).glob(".credentials.json.*.tmp")), [])

    def test_env_var_wins_over_stored_credential(self) -> None:
        from talamus.adapters.llm import AnthropicApiProvider

        captured: dict = {}

        def poster(url: str, headers: dict, payload: dict) -> dict:
            captured["key"] = headers["x-api-key"]
            return {"content": [{"text": "ok"}]}

        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(
                os.environ, {"TALAMUS_HOME": home, "ANTHROPIC_API_KEY": "env-key"}
            ):
                save_credential("anthropic_api_key", "stored-key")
                AnthropicApiProvider(poster=poster).complete("ciao")
        self.assertEqual(captured["key"], "env-key")


if __name__ == "__main__":
    unittest.main()
