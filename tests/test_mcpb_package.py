import json
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path
from typing import Any
from unittest import mock

from scripts.build_smithery_mcpb import _validate_locked_runtime, build_bundle

ROOT = Path(__file__).resolve().parents[1]
MCPB_ROOT = ROOT / "packaging" / "mcpb"


class McpbPackageTests(unittest.TestCase):
    def _manifest(self) -> dict[str, Any]:
        return json.loads((MCPB_ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_bundle_metadata_is_internally_consistent(self) -> None:
        with (MCPB_ROOT / "pyproject.toml").open("rb") as handle:
            launcher = tomllib.load(handle)["project"]
        manifest = self._manifest()

        version = launcher["version"]
        self.assertEqual(version, manifest["version"])
        self.assertEqual([f"talamus[mcp]=={version}"], launcher["dependencies"])

        with (MCPB_ROOT / "uv.lock").open("rb") as handle:
            locked_packages = tomllib.load(handle)["package"]
        talamus = [package for package in locked_packages if package["name"] == "talamus"]
        launcher_lock = next(
            package for package in locked_packages if package["name"] == "talamus-mcpb-launcher"
        )
        self.assertEqual([version], [package["version"] for package in talamus])
        self.assertEqual(
            [
                {
                    "name": "talamus",
                    "extras": ["mcp"],
                    "specifier": f"=={version}",
                }
            ],
            launcher_lock["metadata"]["requires-dist"],
        )

    def test_manifest_references_files_inside_the_bundle(self) -> None:
        manifest = self._manifest()
        server = manifest["server"]

        self.assertEqual("uv", server["type"])
        self.assertTrue((MCPB_ROOT / server["entry_point"]).is_file())
        self.assertTrue((MCPB_ROOT / manifest["icon"]).is_file())
        self.assertTrue((MCPB_ROOT / "README.md").is_file())
        self.assertTrue((MCPB_ROOT / "uv.lock").is_file())
        self.assertIn("${user_config.brain_directory}", server["mcp_config"]["args"])
        self.assertIn("--read-only", server["mcp_config"]["args"])

    def test_manifest_identifies_the_publisher_and_privacy_policy(self) -> None:
        manifest = self._manifest()

        self.assertEqual(
            {"name": "Angio Crapuzzi", "url": "https://github.com/GCrapuzzi"},
            manifest["author"],
        )
        self.assertEqual(
            ["https://ampres-ai.github.io/talamus/privacy/"],
            manifest["privacy_policies"],
        )

    def test_manifest_declares_the_full_mcp_tool_set(self) -> None:
        manifest = self._manifest()
        names = {tool["name"] for tool in manifest["tools"]}
        self.assertEqual(
            {
                "ask",
                "history",
                "ingest_text",
                "neighbors",
                "ontology_status",
                "overview",
                "propose_note",
                "read_note",
                "recall",
                "remember",
                "review_apply",
                "review_list",
                "review_reject",
                "search",
                "sources",
                "verify",
            },
            names,
        )
        mutation_descriptions = {
            tool["name"]: tool["description"]
            for tool in manifest["tools"]
            if tool["name"]
            in {"remember", "ingest_text", "propose_note", "review_apply", "review_reject"}
        }
        self.assertTrue(mutation_descriptions)
        for description in mutation_descriptions.values():
            self.assertIn("--enable-writes", description)

    def test_readme_documents_install_privacy_and_real_examples(self) -> None:
        readme = (MCPB_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("## Install", readme)
        self.assertIn("## Permissions and privacy", readme)
        self.assertIn("https://ampres-ai.github.io/talamus/privacy/", readme)
        self.assertGreaterEqual(readme.count("Expected behavior:"), 3)

    def test_canonical_bundle_keeps_the_user_readme(self) -> None:
        ignored = {
            line.strip()
            for line in (MCPB_ROOT / ".mcpbignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertNotIn("README.md", ignored)

    def test_smithery_bundle_contains_runtime_tool_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "talamus-smithery.mcpb"
            build_bundle(MCPB_ROOT, output)
            with zipfile.ZipFile(output) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                archive_names = archive.namelist()

        self.assertEqual("python", manifest["server"]["type"])
        self.assertEqual("uv", manifest["server"]["mcp_config"]["command"])
        self.assertIn("README.md", archive_names)
        self.assertEqual(16, len(manifest["tools"]))
        for tool in manifest["tools"]:
            self.assertEqual("object", tool["inputSchema"]["type"])
            self.assertEqual("object", tool["outputSchema"]["type"])
            self.assertIn("annotations", tool)

    def test_smithery_builder_rejects_an_unlocked_schema_runtime(self) -> None:
        with mock.patch(
            "scripts.build_smithery_mcpb.importlib_metadata.version",
            return_value="0.0.0",
        ):
            with self.assertRaisesRegex(RuntimeError, "bundle locks"):
                _validate_locked_runtime(MCPB_ROOT)


if __name__ == "__main__":
    unittest.main()
