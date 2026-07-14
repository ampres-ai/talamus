"""Workbench UI-parity endpoints: search bar, capture retry, brain flags,
opencode MCP install — every mutating POST behind the per-launch UI token."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

_HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(_HAS_FASTAPI, "fastapi (ui extra) not installed")
class WorkbenchEndpointTests(unittest.TestCase):
    UI_TOKEN = "test-ui-token"

    def setUp(self) -> None:
        self._home = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(
            os.environ,
            {"TALAMUS_HOME": self._home.name, "TALAMUS_UI_TOKEN": self.UI_TOKEN},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._home.cleanup)

    def _brain(self, tmp: str) -> Path:
        from talamus.config import TalamusConfig, save_config
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        root = Path(tmp)
        paths = TalamusPaths(root)
        paths.ensure_directories()
        save_config(paths.config_path, replace(TalamusConfig.default(), llm_provider="claude-cli"))
        create_demo_brain(paths)
        return root

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

    def test_search_returns_hits_with_zero_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = self._client(self._brain(tmp))

            resp = client.get("/api/search", params={"q": "embedding"})

            self.assertEqual(200, resp.status_code)
            body = resp.json()
            self.assertTrue(body["success"])
            self.assertTrue(body["data"]["hits"])

    def test_mutating_posts_require_the_ui_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bare = self._bare_client(self._brain(tmp))
            for path in ("/api/search/smart", "/api/captures/retry", "/api/brains/flags"):
                resp = bare.post(path, json={})
                self.assertEqual(403, resp.status_code, path)

    def test_captures_lists_pending_sessions(self) -> None:
        from talamus.ingest import save_pending_capture
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            root = self._brain(tmp)
            save_pending_capture(TalamusPaths(root), "transcript", "diff", "usage limit")
            client = self._client(root)

            resp = client.get("/api/captures")

            self.assertEqual(200, resp.status_code)
            self.assertEqual(1, len(resp.json()["data"]["pending"]))

    def test_brains_flags_updates_the_registry(self) -> None:
        from talamus.registry import load_registry, register_brain

        with tempfile.TemporaryDirectory() as tmp:
            root = self._brain(tmp)
            register_brain(root, name="flag-brain")
            client = self._client(root)

            resp = client.post("/api/brains/flags", json={"name": "flag-brain", "sensitive": True})

            self.assertEqual(200, resp.status_code)
            self.assertTrue(resp.json()["success"])
            info = load_registry().by_name("flag-brain")
            assert info is not None
            self.assertTrue(info.sensitive)

    def test_opencode_mcp_install_writes_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._brain(tmp)
            client = self._client(root)

            resp = client.post("/api/integrations/mcp", json={"agent": "opencode"})

            self.assertEqual(200, resp.status_code)
            config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(["talamus-mcp"], config["mcp"]["talamus"]["command"])


if __name__ == "__main__":
    unittest.main()
