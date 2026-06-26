import importlib.util
import tempfile
import unittest
from pathlib import Path

_HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(_HAS_FASTAPI, "fastapi not installed (ui extra)")
class WebApiTests(unittest.TestCase):
    def _client(self, root: Path):
        from fastapi.testclient import TestClient

        from talamus.webapi.app import create_app

        return TestClient(create_app(root))

    def test_readiness_endpoint_returns_service_result(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            create_demo_brain(TalamusPaths(Path(tmp)))
            resp = self._client(Path(tmp)).get("/api/readiness")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIn("data", body)
        self.assertEqual(body["data"]["notes"], 3)

    def test_library_endpoint_lists_notes(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            create_demo_brain(TalamusPaths(Path(tmp)))
            resp = self._client(Path(tmp)).get("/api/library")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(len(body["data"]["notes"]), 3)
        titles = [n["title"] for n in body["data"]["notes"]]
        self.assertIn("Embedding", titles)

    def test_graph_endpoint_lays_out_notes(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            create_demo_brain(TalamusPaths(Path(tmp)))
            resp = self._client(Path(tmp)).get("/api/graph")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertGreaterEqual(len(data["nodes"]), 3)
        node = data["nodes"][0]
        for key in ("id", "label", "x", "y", "r"):
            self.assertIn(key, node)
        self.assertGreaterEqual(len(data["edges"]), 1)

    def test_root_serves_index_or_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resp = self._client(Path(tmp)).get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Talamus", resp.text)


if __name__ == "__main__":
    unittest.main()
