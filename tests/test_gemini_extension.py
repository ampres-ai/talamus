import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GeminiExtensionTests(unittest.TestCase):
    def test_manifest_tracks_the_python_release(self) -> None:
        manifest = json.loads((ROOT / "gemini-extension.json").read_text(encoding="utf-8"))
        with (ROOT / "pyproject.toml").open("rb") as handle:
            version = tomllib.load(handle)["project"]["version"]

        self.assertEqual("talamus", manifest["name"])
        self.assertEqual(version, manifest["version"])
        self.assertEqual(
            {
                "command": "uvx",
                "args": [
                    "--with",
                    "mcp>=1.0",
                    f"talamus=={version}",
                    "mcp",
                    "serve",
                ],
            },
            manifest["mcpServers"]["talamus"],
        )

    def test_manifest_does_not_preapprove_tools_or_embed_secrets(self) -> None:
        manifest = json.loads((ROOT / "gemini-extension.json").read_text(encoding="utf-8"))
        serialized = json.dumps(manifest).lower()

        self.assertNotIn("trust", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("token", serialized)
        self.assertNotIn("password", serialized)


if __name__ == "__main__":
    unittest.main()
