import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from talamus.adapters.llm import (
    engine_command,
    save_credential,
    stored_credential_present,
)
from talamus.config import TalamusConfig, save_config
from talamus.demo import create_demo_brain
from talamus.jobs import JobStore
from talamus.paths import TalamusPaths
from talamus.review import ReviewQueue


class EngineMetadataTests(unittest.TestCase):
    def test_engine_command_exposes_canonical_commands_and_api_sentinel(self) -> None:
        self.assertEqual(engine_command("claude-cli"), "claude")
        self.assertEqual(engine_command("codex-cli"), "codex")
        self.assertEqual(engine_command("gemini-cli"), "gemini")
        self.assertEqual(engine_command("ollama"), "ollama")
        self.assertIsNone(engine_command("anthropic-api"))

    def test_engine_command_preserves_legacy_cli_aliases(self) -> None:
        self.assertEqual(engine_command("codex"), "codex")
        self.assertEqual(engine_command("gemini"), "gemini")
        self.assertIsNone(engine_command("api"))

    def test_public_engine_metadata_is_canonical(self) -> None:
        from talamus.adapters.llm import ENGINE_COMMANDS, ENGINE_LABELS

        legacy_aliases = {"codex", "gemini", "api"}
        self.assertFalse(legacy_aliases & set(ENGINE_COMMANDS))
        self.assertFalse(legacy_aliases & set(ENGINE_LABELS))

    def test_stored_credential_present_returns_bool_without_exposing_secret(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}):
                self.assertIs(stored_credential_present("anthropic_api_key"), False)
                save_credential("anthropic_api_key", "sk-secret-test")

                result = stored_credential_present("anthropic_api_key")

        self.assertIs(result, True)
        self.assertIsInstance(result, bool)
        self.assertNotEqual(result, "sk-secret-test")


class ReadinessServiceTests(unittest.TestCase):
    def test_empty_workspace_inspection_does_not_create_config(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            root = Path(tmp)
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                report = inspect_readiness(root=str(root), cwd=root)

            self.assertFalse((root / "talamus.json").exists())
            self.assertFalse((root / ".talamus").exists())
            self.assertFalse(report.config_exists)
            self.assertEqual(root.resolve(), Path(report.root))
            self.assertEqual(
                ["open_brain", "try_demo", "create_brain"],
                [action.action_id for action in report.next_actions],
            )
            self.assertEqual(
                ["brains", "demo", "brains"], [action.target for action in report.next_actions]
            )
            self.assertIsInstance(report.registered_brains, int)

            payload = report.to_dict()
            self.assertEqual(str(root.resolve()), payload["root"])
            self.assertIsInstance(payload["registered_brains"], int)
            self.assertEqual(
                ["open_brain", "try_demo", "create_brain"],
                [action["action_id"] for action in payload["next_actions"]],
            )

    def test_legacy_configured_engine_alias_maps_to_canonical_metadata(self) -> None:
        from talamus.services.readiness import inspect_engines, inspect_readiness

        def which(command: str) -> str | None:
            return command if command == "codex" else None

        with mock.patch("talamus.services.readiness.shutil.which", side_effect=which):
            engines = inspect_engines("codex")

        codex = next(engine for engine in engines if engine.provider == "codex-cli")
        self.assertTrue(codex.configured)
        self.assertTrue(codex.available)
        self.assertFalse(any(engine.provider == "codex" for engine in engines))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            config = json.loads(paths.config_path.read_text(encoding="utf-8"))
            config["llm_provider"] = "codex"
            paths.config_path.write_text(json.dumps(config), encoding="utf-8")
            with mock.patch("talamus.services.readiness.shutil.which", side_effect=which):
                report = inspect_readiness(root=str(root), cwd=root)

        self.assertEqual("codex-cli", report.selected_engine)
        self.assertEqual("codex-cli", report.to_dict()["selected_engine"])

    def test_malformed_config_degrades_to_report_with_error(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            paths.config_path.write_text("{not-json", encoding="utf-8")

            report = inspect_readiness(root=str(root), cwd=root)

        self.assertTrue(report.config_exists)
        self.assertTrue(report.config_error)
        self.assertEqual("claude-cli", report.selected_engine)

    def test_corrupt_derived_cache_degrades_to_empty_counts(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            paths.cache.mkdir(parents=True)
            paths.overview_file.write_text("{not-json", encoding="utf-8")
            review_dir = paths.cache / "review"
            review_dir.mkdir()
            (review_dir / "bad.json").write_text('{"item_id": "bad"}', encoding="utf-8")
            jobs_dir = paths.cache / "jobs"
            jobs_dir.mkdir()
            (jobs_dir / "bad.json").write_text('{"job_id": "bad"}', encoding="utf-8")

            report = inspect_readiness(root=str(root), cwd=root)

        self.assertEqual(0, report.overview_domains)
        self.assertFalse(report.overview_built)
        self.assertEqual(0, report.reviews_pending)
        self.assertEqual(0, report.jobs_active)

    def test_wrong_shaped_derived_json_degrades_to_empty_counts(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            paths.cache.mkdir(parents=True)
            paths.overview_file.write_text("null", encoding="utf-8")
            review_dir = paths.cache / "review"
            review_dir.mkdir()
            (review_dir / "bad.json").write_text("[]", encoding="utf-8")
            jobs_dir = paths.cache / "jobs"
            jobs_dir.mkdir()
            (jobs_dir / "bad.json").write_text("[]", encoding="utf-8")
            (root / ".mcp.json").write_text("[]", encoding="utf-8")

            report = inspect_readiness(root=str(root), cwd=root)

        self.assertEqual(0, report.overview_domains)
        self.assertFalse(report.overview_built)
        self.assertEqual(0, report.reviews_pending)
        self.assertEqual(0, report.jobs_active)
        self.assertFalse(report.mcp_installed)

    def test_wrong_shaped_credentials_json_degrades_to_api_key_needed(self) -> None:
        from talamus.services.readiness import inspect_engines, inspect_readiness

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            (Path(home) / "credentials.json").write_text("[]", encoding="utf-8")

            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                os.environ.pop("ANTHROPIC_API_KEY", None)
                engines = inspect_engines("anthropic-api")
                report = inspect_readiness(root=str(root), cwd=root)

        api_direct = next(engine for engine in engines if engine.provider == "anthropic-api")
        self.assertFalse(api_direct.available)
        self.assertTrue(api_direct.needs_secret)
        api = next(engine for engine in report.engines if engine.provider == "anthropic-api")
        self.assertFalse(api.available)
        self.assertTrue(api.needs_secret)
        self.assertEqual("needs_secret", api.status)

    def test_malformed_registry_degrades_to_zero_registered_brains(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            registry_path = Path(home) / "registry.json"
            registry_path.write_text(json.dumps({"brains": [{"name": "broken"}]}), encoding="utf-8")

            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                report = inspect_readiness(root=str(root), cwd=root)

        self.assertEqual(0, report.registered_brains)
        self.assertEqual("", report.selected_brain)

    def test_malformed_registry_degrades_during_implicit_resolution(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as home:
            registry_path = Path(home) / "registry.json"
            registry_path.write_text(json.dumps({"brains": [{"name": "broken"}]}), encoding="utf-8")

            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                report = inspect_readiness(cwd=Path(cwd))
                named = inspect_readiness(brain="named-brain", cwd=Path(cwd))

        self.assertEqual(str((Path(home) / "default").resolve()), report.root)
        self.assertFalse(report.config_exists)
        self.assertEqual(str((Path(home) / "named-brain").resolve()), named.root)
        self.assertFalse(named.config_exists)

    def test_wrong_shaped_registry_json_degrades_to_empty_registry(self) -> None:
        from talamus.services.readiness import inspect_readiness

        for payload in ("[]", json.dumps({"brains": "not-a-list"})):
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
                    root = Path(tmp)
                    paths = TalamusPaths(root)
                    save_config(paths.config_path, TalamusConfig.default())
                    (Path(home) / "registry.json").write_text(payload, encoding="utf-8")

                    with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                        report = inspect_readiness(root=str(root), cwd=root)

                self.assertEqual(0, report.registered_brains)
                self.assertEqual("", report.selected_brain)

    def test_wrong_typed_config_values_degrade_to_default_text_fields(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            data = json.loads(paths.config_path.read_text(encoding="utf-8"))
            data["llm_provider"] = []
            data["llm_model"] = {"model": "bad"}
            paths.config_path.write_text(json.dumps(data), encoding="utf-8")

            report = inspect_readiness(root=str(root), cwd=root)

        self.assertTrue(report.config_error)
        self.assertEqual("claude-cli", report.selected_engine)
        self.assertEqual("", report.selected_model)

    def test_unavailable_selected_engine_suggests_system_configuration(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            with (
                mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False),
                mock.patch("talamus.services.readiness.shutil.which", return_value=None),
            ):
                report = inspect_readiness(root=str(root), cwd=root)

        configure = next(
            action for action in report.next_actions if action.action_id == "configure_engine"
        )
        self.assertEqual("system", configure.target)

    def test_demo_brain_reports_work_waiting_and_current_indexes(self) -> None:
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            create_demo_brain(paths)
            ReviewQueue(paths).add("low_confidence_note", "Review demo note", {})
            JobStore(paths).create("import", {"path": "demo"})

            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                report = inspect_readiness(root=str(root), cwd=root)

            self.assertTrue(report.config_exists)
            self.assertGreaterEqual(report.notes, 1)
            self.assertEqual(1, report.reviews_pending)
            self.assertEqual(1, report.jobs_active)
            self.assertTrue(report.cache_current)
            self.assertNotEqual("none", report.index_backend)

    def test_readiness_routes_pending_ontology_candidates(self) -> None:
        from talamus.ontology_lab import RelationType, Schema, save_schema
        from talamus.services.readiness import inspect_readiness

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            save_config(paths.config_path, TalamusConfig.default())
            create_demo_brain(paths)
            save_schema(
                paths,
                Schema(
                    relation_types=[
                        RelationType(
                            id="rel:alimenta",
                            name="alimenta",
                            status="candidate",
                            support=3,
                        )
                    ]
                ),
            )

            report = inspect_readiness(root=str(root), cwd=root)

        self.assertEqual(1, report.ontology_candidates)
        payload = report.to_dict()
        self.assertEqual(1, payload["ontology_candidates"])
        ontology = next(
            action for action in report.next_actions if action.action_id == "review_ontology"
        )
        self.assertEqual("ontology", ontology.target)


if __name__ == "__main__":
    unittest.main()
