import json
import tomllib
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MCPB_ROOT = ROOT / "packaging" / "mcpb"


class McpbPackageTests(unittest.TestCase):
    def _manifest(self) -> dict[str, Any]:
        return json.loads((MCPB_ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_bundle_metadata_tracks_the_python_release(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        with (MCPB_ROOT / "pyproject.toml").open("rb") as handle:
            launcher = tomllib.load(handle)["project"]
        manifest = self._manifest()

        version = project["version"]
        self.assertEqual(version, manifest["version"])
        self.assertEqual(version, launcher["version"])
        self.assertEqual([f"talamus[mcp]=={version}"], launcher["dependencies"])

    def test_manifest_references_files_inside_the_bundle(self) -> None:
        manifest = self._manifest()
        server = manifest["server"]

        self.assertEqual("uv", server["type"])
        self.assertTrue((MCPB_ROOT / server["entry_point"]).is_file())
        self.assertTrue((MCPB_ROOT / manifest["icon"]).is_file())
        self.assertTrue((MCPB_ROOT / "uv.lock").is_file())
        self.assertIn("${user_config.brain_directory}", server["mcp_config"]["args"])

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


if __name__ == "__main__":
    unittest.main()
