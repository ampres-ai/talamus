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

    def test_note_endpoint_returns_markdown(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            create_demo_brain(TalamusPaths(Path(tmp)))
            resp = self._client(Path(tmp)).get("/api/note", params={"title": "Embedding"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["data"]["found"])
        self.assertIn("Embedding", body["data"]["markdown"])

    def _seed_review(self, root: Path, kind: str, title: str, detail: dict) -> str:
        from talamus.paths import TalamusPaths
        from talamus.review import ReviewQueue

        return ReviewQueue(TalamusPaths(root)).add(kind, title, detail).item_id

    def test_review_endpoint_lists_pending_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_review(root, "correction", "Fix the RAG note", {"title": "RAG"})
            resp = self._client(root).get("/api/review")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(len(body["data"]), 1)
        item = body["data"][0]
        for key in ("item_id", "kind", "title", "status", "created_at", "detail"):
            self.assertIn(key, item)
        self.assertEqual(item["kind"], "correction")
        self.assertEqual(item["status"], "pending")
        self.assertEqual(item["detail"]["title"], "RAG")

    def test_review_apply_endpoint_resolves_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item_id = self._seed_review(
                root, "low_confidence_note", "Maybe a note", {"reason": "confidence 0.3"}
            )
            client = self._client(root)
            resp = client.post(f"/api/review/{item_id}/apply")
            listed = client.get("/api/review").json()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "applied")
        self.assertEqual(listed["data"], [])  # no longer pending

    def test_review_reject_endpoint_records_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item_id = self._seed_review(
                root, "stale_source", "Old source", {"reason": "hash changed"}
            )
            resp = self._client(root).post(
                f"/api/review/{item_id}/reject", json={"reason": "still valid"}
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "rejected")
        self.assertEqual(body["data"]["resolution"], "still valid")

    def test_ask_endpoint_rejects_empty_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resp = self._client(Path(tmp)).post("/api/ask", json={"question": "  "})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual("ask_empty", body["code"])

    def test_ask_endpoint_degrades_to_sources_without_engine(self) -> None:
        from unittest.mock import patch

        from talamus.demo import create_demo_brain
        from talamus.errors import EngineNotFound
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            with patch("talamus.services.ask.build_provider", side_effect=EngineNotFound("none")):
                resp = self._client(root).post("/api/ask", json={"question": "what is reranking?"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual("ask_no_engine", body["code"])
        self.assertFalse(body["data"]["answered"])
        self.assertTrue(body["data"]["sources"])

    def _seed_ontology_candidate(self, root: Path, type_id: str, name: str) -> str:
        from talamus.ontology_lab import RelationType, load_schema, save_schema
        from talamus.paths import TalamusPaths

        paths = TalamusPaths(root)
        schema = load_schema(paths)
        schema.relation_types.append(
            RelationType(
                id=type_id,
                name=name,
                definition=f"{name}: A relates to B",
                examples=[f"RAG {name} fine-tuning"],
                support=3,
                distinct_notes=2,
                confidence=0.62,
                status="candidate",
            )
        )
        save_schema(paths, schema)
        return type_id

    def test_ontology_status_endpoint_returns_coverage(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            create_demo_brain(TalamusPaths(Path(tmp)))
            resp = self._client(Path(tmp)).get("/api/ontology/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        for key in ("schema_id", "version", "coverage"):
            self.assertIn(key, body["data"])

    def test_ontology_candidates_listed_and_promoted(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            type_id = self._seed_ontology_candidate(root, "rel:contrasts", "contrasts")
            client = self._client(root)
            listed = client.get("/api/ontology/types", params={"status": "candidate"}).json()
            promoted = client.post(f"/api/ontology/{type_id}/promote")
            after = client.get("/api/ontology/types", params={"status": "active"}).json()
        self.assertEqual(len(listed["data"]), 1)
        self.assertEqual(listed["data"][0]["name"], "contrasts")
        self.assertEqual(promoted.status_code, 200)
        self.assertTrue(promoted.json()["success"])
        self.assertIn("contrasts", [t["name"] for t in after["data"]])

    def test_ontology_reject_endpoint_records_decision(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            type_id = self._seed_ontology_candidate(root, "rel:echoes", "echoes")
            resp = self._client(root).post(
                f"/api/ontology/{type_id}/reject", json={"reason": "too vague"}
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertEqual("rejected", resp.json()["data"]["action"])

    def test_diagnostics_endpoint_reports_healthy_demo(self) -> None:
        from talamus.config import TalamusConfig, save_config
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            create_demo_brain(paths)
            save_config(paths.config_path, TalamusConfig.default())
            resp = self._client(Path(tmp)).get("/api/diagnostics")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        data = body["data"]
        self.assertTrue(data["ok"])
        self.assertEqual(data["notes"], 3)
        self.assertEqual(data["index_backend"], "sqlite-fts5")
        self.assertTrue(any(c["label"] == "Config" for c in data["checks"]))

    def test_diagnostics_endpoint_flags_uninitialized_brain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resp = self._client(Path(tmp)).get("/api/diagnostics")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual("diagnostics_not_initialized", body["code"])
        self.assertIn("checks", body["data"])

    def test_brains_endpoint_lists_registry(self) -> None:
        import os
        from unittest.mock import patch

        from talamus.registry import register_brain, select_brain

        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as brain_root,
        ):
            root = Path(brain_root)
            (root / "talamus.json").write_text("{}", encoding="utf-8")
            (root / "notes").mkdir()
            register_brain(root, name="alpha", home=Path(home))
            select_brain("alpha", home=Path(home))
            with patch.dict(os.environ, {"TALAMUS_HOME": home}):
                resp = self._client(Path(brain_root)).get("/api/brains")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        data = body["data"]
        self.assertEqual(data["selected"], "alpha")
        self.assertEqual(data["brains"][0]["name"], "alpha")
        self.assertIn("brains", data)

    def test_import_preview_estimates_a_file(self) -> None:
        from talamus.config import TalamusConfig, save_config
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            save_config(TalamusPaths(root).config_path, TalamusConfig.default())
            source = root / "import_me.md"
            source.write_text("# Topic\n" + ("some prose about retrieval. " * 40), encoding="utf-8")
            resp = self._client(root).post("/api/import/preview", json={"target": str(source)})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["code"], "ingest_preview_ready")
        for key in ("chunks", "est_llm_calls", "est_input_tokens", "requires_confirmation"):
            self.assertIn(key, body["data"])

    def test_scan_preview_lists_files(self) -> None:
        from talamus.config import TalamusConfig, save_config
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as src:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            save_config(TalamusPaths(root).config_path, TalamusConfig.default())
            (Path(src) / "a.md").write_text("# A\n" + ("text " * 50), encoding="utf-8")
            (Path(src) / "b.txt").write_text("hello " * 40, encoding="utf-8")
            resp = self._client(root).post("/api/scan/preview", json={"target": src})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["code"], "scan_preview_ready")
        self.assertGreaterEqual(body["data"]["files"], 2)

    def test_scan_run_requires_confirmation(self) -> None:
        from talamus.config import TalamusConfig, save_config
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as src:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            save_config(TalamusPaths(root).config_path, TalamusConfig.default())
            (Path(src) / "a.md").write_text("# A\n" + ("text " * 50), encoding="utf-8")
            resp = self._client(root).post(
                "/api/scan/run", json={"target": src, "confirmed": False}
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["code"], "scan_confirmation_required")

    def test_active_endpoint_reports_current_brain(self) -> None:
        from talamus.config import TalamusConfig, save_config
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            save_config(TalamusPaths(root).config_path, TalamusConfig.default())
            resp = self._client(root).get("/api/active")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["data"]["initialized"])
        self.assertEqual(body["data"]["notes"], 3)

    def test_set_active_switches_to_another_brain(self) -> None:
        import os
        from unittest.mock import patch

        from talamus.config import TalamusConfig, save_config
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as a,
            tempfile.TemporaryDirectory() as b,
        ):
            for d in (a, b):
                create_demo_brain(TalamusPaths(Path(d)))
                save_config(TalamusPaths(Path(d)).config_path, TalamusConfig.default())
            client = self._client(Path(a))  # workbench launched against brain A
            with patch.dict(os.environ, {"TALAMUS_HOME": home}):
                switched = client.post("/api/active", json={"path": b}).json()
                now = client.get("/api/active").json()
        self.assertTrue(switched["success"])
        self.assertEqual(switched["code"], "brain_activated")
        self.assertEqual(Path(now["data"]["path"]), Path(b).resolve())  # root really moved

    def test_set_active_rejects_a_non_brain_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as empty:
            resp = self._client(Path(tmp)).post("/api/active", json={"path": empty})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "brain_not_initialized")

    def test_root_serves_index_or_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resp = self._client(Path(tmp)).get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Talamus", resp.text)


if __name__ == "__main__":
    unittest.main()
