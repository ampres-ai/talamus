import json
import re
import tomllib
import unittest
from pathlib import Path

import talamus

ROOT = Path(__file__).resolve().parents[1]
PIN_PATTERN = re.compile(r"(?:talamus(?:\[mcp\])?==|ghcr\.io/ampres-ai/talamus:)(\d+\.\d+\.\d+)")


class PackagingTests(unittest.TestCase):
    def test_py_typed_marker_ships(self) -> None:
        """PEP 561: the marker must sit next to the package so SDK users get types."""
        marker = Path(talamus.__file__).parent / "py.typed"
        self.assertTrue(marker.is_file())

    def test_version_is_exposed(self) -> None:
        self.assertTrue(talamus.__version__)

    def test_release_metadata_is_consistent(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            version = tomllib.load(handle)["project"]["version"]

        server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
        goose = json.loads((ROOT / ".goose-plugin" / "plugin.json").read_text(encoding="utf-8"))
        gemini = json.loads((ROOT / "gemini-extension.json").read_text(encoding="utf-8"))
        claude_mcp = json.loads(
            (ROOT / "plugins" / "talamus-memory" / ".mcp.json").read_text(encoding="utf-8")
        )
        goose_mcp = json.loads(
            (ROOT / "plugins" / "talamus-memory" / ".goose-mcp.json").read_text(encoding="utf-8")
        )

        self.assertEqual(version, talamus.__version__)
        self.assertEqual(version, server["version"])
        self.assertEqual(version, server["packages"][0]["version"])
        self.assertEqual(version, goose["version"])
        self.assertEqual(version, gemini["version"])
        self.assertIn(f"talamus=={version}", gemini["mcpServers"]["talamus"]["args"])
        expected_mcp_pin = f"talamus[mcp]=={version}"
        self.assertIn(expected_mcp_pin, claude_mcp["mcpServers"]["talamus"]["args"])
        self.assertIn(expected_mcp_pin, goose_mcp["mcpServers"]["talamus"]["args"])

        pinned_docs = (
            ROOT / "README.md",
            ROOT / "docs" / "submissions" / "openai-talamus-memory-v1.md",
            ROOT / "plugins" / "talamus-memory" / "README.md",
            ROOT / "plugins" / "talamus-memory" / "skills" / "talamus-memory" / "SKILL.md",
            ROOT / "plugins" / "talamus-memory" / "cursor-skills" / "talamus-memory" / "SKILL.md",
            ROOT
            / "plugins"
            / "openai"
            / "talamus-memory"
            / "skills"
            / "talamus-memory"
            / "SKILL.md",
        )
        for path in pinned_docs:
            with self.subTest(path=path.relative_to(ROOT)):
                pins = PIN_PATTERN.findall(path.read_text(encoding="utf-8"))
                self.assertTrue(pins)
                self.assertEqual({version}, set(pins))


if __name__ == "__main__":
    unittest.main()
