import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from talamus.config import TalamusConfig, load_config, save_config
from talamus.paths import TalamusPaths


class ServiceResultTests(unittest.TestCase):
    def test_service_result_serializes_public_contract(self) -> None:
        from talamus.services.result import ServiceResult

        result = ServiceResult[dict[str, str]](
            success=True,
            message="Engine settings saved",
            code="engine_settings_saved",
            data={"llm_provider": "codex-cli"},
        )

        self.assertEqual(
            {
                "success": True,
                "message": "Engine settings saved",
                "code": "engine_settings_saved",
                "data": {"llm_provider": "codex-cli"},
            },
            result.to_dict(),
        )


class EngineSetupServiceTests(unittest.TestCase):
    def test_engine_listing_exposes_canonical_ids_and_statuses(self) -> None:
        from talamus.services.engines import list_engines

        def which(command: str) -> str | None:
            return f"/bin/{command}" if command == "codex" else None

        with mock.patch("talamus.services.readiness.shutil.which", side_effect=which):
            engines = list_engines(selected_provider="codex", selected_model="gpt-fast")

        providers = [engine.provider for engine in engines]
        self.assertIn("codex-cli", providers)
        self.assertNotIn("codex", providers)
        self.assertNotIn("gemini", providers)
        self.assertNotIn("api", providers)

        codex = next(engine for engine in engines if engine.provider == "codex-cli")
        self.assertEqual("Codex CLI", codex.label)
        self.assertTrue(codex.available)
        self.assertTrue(codex.configured)
        self.assertEqual("ready", codex.status)
        self.assertIn("gpt-fast", codex.detail)

    def test_choose_default_engine_uses_metadata_order_and_falls_back_to_claude(self) -> None:
        from talamus.services.engines import choose_default_engine

        def which(command: str) -> str | None:
            return f"/bin/{command}" if command == "gemini" else None

        with mock.patch("talamus.services.readiness.shutil.which", side_effect=which):
            self.assertEqual("gemini-cli", choose_default_engine())

        with mock.patch("talamus.services.readiness.shutil.which", return_value=None):
            self.assertEqual("claude-cli", choose_default_engine())

    def test_engine_settings_roundtrip_preserves_unrelated_config_fields(self) -> None:
        from talamus.services.engines import load_engine_settings, update_engine_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            original = replace(
                TalamusConfig.default(),
                storage_provider="custom-storage",
                search_provider="custom-search",
                llm_provider="claude-cli",
                llm_model="old-model",
                language="Italian",
            )
            save_config(paths.config_path, original)

            result = update_engine_settings(
                root,
                provider="gemini",
                model="gemini-2.5-flash",
                language="German",
            )

            self.assertTrue(result.success)
            self.assertEqual("engine_settings_saved", result.code)
            self.assertEqual(
                {
                    "llm_provider": "gemini-cli",
                    "llm_model": "gemini-2.5-flash",
                    "language": "German",
                },
                result.data,
            )
            config = load_config(paths.config_path)
            self.assertEqual("custom-storage", config.storage_provider)
            self.assertEqual("custom-search", config.search_provider)
            self.assertEqual("gemini-cli", config.llm_provider)
            self.assertEqual("gemini-2.5-flash", config.llm_model)
            self.assertEqual("German", config.language)

            loaded = load_engine_settings(root)

        self.assertTrue(loaded.success)
        self.assertEqual(
            {
                "llm_provider": "gemini-cli",
                "llm_model": "gemini-2.5-flash",
                "language": "German",
            },
            loaded.data,
        )

    def test_engine_settings_update_normalizes_existing_alias(self) -> None:
        from talamus.services.engines import update_engine_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            original = replace(TalamusConfig.default(), llm_provider="codex")
            save_config(paths.config_path, original)

            result = update_engine_settings(root, model="gpt-fast")

            config = load_config(paths.config_path)

        self.assertTrue(result.success)
        self.assertEqual("codex-cli", config.llm_provider)
        self.assertEqual("gpt-fast", config.llm_model)
        self.assertEqual("codex-cli", result.data["llm_provider"])

    def test_engine_settings_update_does_not_persist_unrelated_env_overrides(self) -> None:
        from talamus.services.engines import update_engine_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            original = replace(TalamusConfig.default(), storage_provider="disk-storage")
            save_config(paths.config_path, original)

            with mock.patch.dict(
                os.environ, {"TALAMUS_STORAGE_PROVIDER": "env-storage"}, clear=False
            ):
                result = update_engine_settings(root, provider="ollama", model="llama3")

            config = load_config(paths.config_path)

        self.assertTrue(result.success)
        self.assertEqual("disk-storage", config.storage_provider)
        self.assertEqual("ollama", config.llm_provider)
        self.assertEqual("llama3", config.llm_model)

    def test_malformed_config_returns_failed_engine_settings_results(self) -> None:
        from talamus.services.engines import load_engine_settings, update_engine_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            original = "{not-json"
            paths.config_path.write_text(original, encoding="utf-8")

            loaded = load_engine_settings(root)
            updated = update_engine_settings(root, provider="ollama")
            after = paths.config_path.read_text(encoding="utf-8")

        self.assertFalse(loaded.success)
        self.assertEqual("engine_settings_invalid_config", loaded.code)
        self.assertFalse(updated.success)
        self.assertEqual("engine_settings_invalid_config", updated.code)
        self.assertEqual(original, after)

    def test_unsupported_provider_returns_failure_and_leaves_config_unchanged(self) -> None:
        from talamus.services.engines import update_engine_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            original = replace(
                TalamusConfig.default(),
                llm_provider="codex-cli",
                llm_model="gpt-fast",
                language="Italian",
            )
            save_config(paths.config_path, original)
            before = paths.config_path.read_text(encoding="utf-8")

            result = update_engine_settings(root, provider="unsupported-engine", model="new-model")
            after = paths.config_path.read_text(encoding="utf-8")
            config = load_config(paths.config_path)

        self.assertFalse(result.success)
        self.assertEqual("unsupported_provider", result.code)
        self.assertEqual(before, after)
        self.assertEqual("codex-cli", config.llm_provider)
        self.assertEqual("gpt-fast", config.llm_model)
        self.assertEqual("Italian", config.language)

    def test_save_anthropic_api_key_never_returns_secret(self) -> None:
        from talamus.adapters.llm import stored_credential_present
        from talamus.services.engines import save_anthropic_api_key

        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}, clear=False):
                result = save_anthropic_api_key("sk-secret-value")
                credential_file = Path(home) / "credentials.json"
                stored = json.loads(credential_file.read_text(encoding="utf-8"))
                present = stored_credential_present("anthropic_api_key")

        self.assertTrue(result.success)
        self.assertEqual("anthropic_api_key_saved", result.code)
        self.assertTrue(present)
        self.assertEqual("sk-secret-value", stored["anthropic_api_key"])
        self.assertNotIn("sk-secret-value", json.dumps(result.to_dict()))


if __name__ == "__main__":
    unittest.main()
