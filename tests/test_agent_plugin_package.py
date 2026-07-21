from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "talamus-memory"


class AgentPluginPackageTests(unittest.TestCase):
    def test_copilot_and_claude_manifests_match(self) -> None:
        copilot = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
        claude = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(copilot, claude)

    def test_mcp_launcher_pins_the_current_package_version(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        args = config["mcpServers"]["talamus"]["args"]

        self.assertEqual(f"talamus[mcp]=={project['project']['version']}", args[1])


if __name__ == "__main__":
    unittest.main()
