"""UI-parity endpoints (integrations + engine probe). Every /api call sits behind
the S1 guard (per-launch token + Origin check) — the tests assert both the happy
path WITH the token and the 403 without it."""

import importlib.util
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

_HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(_HAS_FASTAPI, "fastapi not installed (ui extra)")
class WebApiParityTests(unittest.TestCase):
    UI_TOKEN = "test-ui-token"

    def setUp(self) -> None:
        # isolate TALAMUS_HOME per test and pin the workbench token so the
        # client can authenticate deterministically (same as test_webapi.py)
        self._home = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(
            os.environ,
            {"TALAMUS_HOME": self._home.name, "TALAMUS_UI_TOKEN": self.UI_TOKEN},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._home.cleanup)

    def _client(self, root: Path):
        from fastapi.testclient import TestClient

        from talamus.webapi.app import create_app

        return TestClient(
            create_app(root),
            base_url="http://127.0.0.1",
            headers={"X-Talamus-UI": self.UI_TOKEN},
        )

    def _bare_client(self, root: Path):
        from fastapi.testclient import TestClient

        from talamus.webapi.app import create_app

        return TestClient(create_app(root), base_url="http://127.0.0.1")

    # --- GET /api/integrations -------------------------------------------------

    def test_integrations_get_reports_cursor_codex_and_hook_status(self) -> None:
        from talamus.services.integrations import (
            install_capture_hook,
            install_mcp_config_cursor,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_mcp_config_cursor(root)
            install_capture_hook(root)
            with mock.patch("talamus.services.integrations.shutil.which", return_value="codex"):
                resp = self._client(root).get("/api/integrations")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"], body)
        data = body["data"]
        self.assertFalse(data["mcp_installed"])
        self.assertTrue(data["cursor_installed"])
        self.assertTrue(data["codex_on_path"])
        self.assertTrue(data["hook_installed"])

    # --- POST /api/integrations/mcp --------------------------------------------

    def test_integrations_mcp_post_requires_s1_token_and_writes_claude_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rejected = self._bare_client(root).post(
                "/api/integrations/mcp", json={"agent": "claude"}
            )

            installed = self._client(root).post("/api/integrations/mcp", json={"agent": "claude"})
            config = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))

        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(installed.status_code, 200)
        body = installed.json()
        self.assertTrue(body["success"], body)
        self.assertTrue(body["data"]["results"]["claude"]["success"])
        self.assertEqual("talamus-mcp", config["mcpServers"]["talamus"]["command"])

    def test_integrations_mcp_auto_skips_codex_when_not_on_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch("talamus.services.integrations.shutil.which", return_value=None):
                resp = self._client(root).post("/api/integrations/mcp", json={"agent": "auto"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"], body)
        results = body["data"]["results"]
        self.assertIn("claude", results)
        self.assertNotIn("codex", results)  # auto = attempt codex only when on PATH
        self.assertNotIn("cursor", results)  # no .cursor/ dir in the temp brain

    def test_integrations_mcp_rejects_an_unknown_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resp = self._client(Path(tmp)).post("/api/integrations/mcp", json={"agent": "vim"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual("mcp_agent_unknown", body["code"])

    # --- POST /api/integrations/hook --------------------------------------------

    def test_integrations_hook_post_requires_s1_origin_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = self._client(Path(tmp))
            rejected = client.post(
                "/api/integrations/hook",
                headers={"Origin": "https://evil.test"},
            )
            installed = client.post("/api/integrations/hook")

        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()["code"], "forbidden_origin")
        self.assertEqual(installed.status_code, 200)
        self.assertTrue(installed.json()["success"], installed.json())
        self.assertEqual("hook_installed", installed.json()["code"])

    # --- POST /api/engines/probe --------------------------------------------------

    def _probe_config(self, root: Path) -> None:
        from talamus.config import TalamusConfig, save_config
        from talamus.paths import TalamusPaths

        save_config(
            TalamusPaths(root).config_path,
            replace(TalamusConfig.default(), llm_provider="claude-cli", llm_model="haiku"),
        )

    def test_engine_probe_post_uses_fake_provider_and_returns_verified(self) -> None:
        class FakeProvider:
            def complete(self, prompt: str) -> str:
                self.prompt = prompt
                return "ok"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._probe_config(root)
            with mock.patch(
                "talamus.services.engines.build_provider", return_value=FakeProvider()
            ) as built:
                resp = self._client(root).post("/api/engines/probe", json={"engine": "claude-cli"})

        self.assertEqual(resp.status_code, 200)
        built.assert_called_once_with("claude-cli", "haiku")
        body = resp.json()
        self.assertTrue(body["success"], body)
        self.assertTrue(body["data"]["verified"])
        self.assertEqual("ok", body["data"]["answer"])
        self.assertFalse(body["data"]["limit_reached"])
        self.assertIn("claude", body["data"]["hint"])

    def test_engine_probe_post_reports_limit_reached(self) -> None:
        from talamus.errors import EngineLimitReached

        class LimitedProvider:
            def complete(self, prompt: str) -> str:
                raise EngineLimitReached("usage limit reached — resets at 18:00")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._probe_config(root)
            with mock.patch(
                "talamus.services.engines.build_provider", return_value=LimitedProvider()
            ):
                resp = self._client(root).post("/api/engines/probe", json={"engine": "claude-cli"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual("engine_limit_reached", body["code"])
        data = body["data"]
        self.assertFalse(data["verified"])
        self.assertTrue(data["limit_reached"])
        self.assertIn("usage limit", data["error"])
        # a hit limit must NOT get the login hint — it points at the reset/switch
        self.assertIn("limit", data["hint"].lower())
        self.assertNotIn("log in", data["hint"].lower())

    def test_engine_probe_post_reports_failure_with_hint(self) -> None:
        from talamus.errors import EngineFailed

        class DownProvider:
            def complete(self, prompt: str) -> str:
                raise EngineFailed("boom: engine unreachable")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._probe_config(root)
            with mock.patch("talamus.services.engines.build_provider", return_value=DownProvider()):
                resp = self._client(root).post("/api/engines/probe", json={"engine": "opencode"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual("engine_not_verified", body["code"])
        data = body["data"]
        self.assertFalse(data["verified"])
        self.assertFalse(data["limit_reached"])
        self.assertIn("boom", data["error"])
        self.assertIn("opencode auth login", data["hint"])

    def test_engine_probe_post_rejects_an_unsupported_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._probe_config(root)
            resp = self._client(root).post("/api/engines/probe", json={"engine": "flurble"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual("unsupported_provider", body["code"])

    def test_engine_probe_post_requires_s1_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resp = self._bare_client(Path(tmp)).post(
                "/api/engines/probe", json={"engine": "claude-cli"}
            )

        self.assertEqual(resp.status_code, 403)

    def test_engine_select_post_switches_the_active_engine(self) -> None:
        from talamus.config import load_config
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._probe_config(root)  # starts on claude-cli
            resp = self._client(root).post("/api/engines/select", json={"engine": "codex-cli"})
            saved = load_config(TalamusPaths(root).config_path).llm_provider

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"], resp.json())
        self.assertEqual("codex-cli", saved)

    def test_engine_select_post_rejects_unsupported_and_requires_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._probe_config(root)
            bad = self._client(root).post("/api/engines/select", json={"engine": "flurble"})
            self.assertFalse(bad.json()["success"])
            self.assertEqual("unsupported_provider", bad.json()["code"])

            rejected = self._bare_client(root).post(
                "/api/engines/select", json={"engine": "codex-cli"}
            )
            self.assertEqual(rejected.status_code, 403)

    def test_reindex_post_rebuilds_cache_and_requires_token(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            ok = self._client(root).post("/api/reindex")
            self.assertEqual(ok.status_code, 200)
            body = ok.json()
            self.assertTrue(body["success"], body)
            self.assertEqual("reindexed", body["code"])
            self.assertGreaterEqual(body["data"]["reindexed"], 0)

            rejected = self._bare_client(root).post("/api/reindex")
            self.assertEqual(rejected.status_code, 403)


if __name__ == "__main__":
    unittest.main()
