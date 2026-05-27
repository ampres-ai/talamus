import tempfile
import unittest
from pathlib import Path

from brain.config import BrainConfig, load_config, save_config
from brain.paths import BrainPaths


class BrainPathsConfigTests(unittest.TestCase):
    def test_default_paths_are_generic(self) -> None:
        paths = BrainPaths(Path("C:/project"))

        self.assertEqual(paths.project_root, Path("C:/project"))
        self.assertEqual(paths.knowledge, Path("C:/project") / "knowledge")
        self.assertEqual(paths.raw, Path("C:/project") / "knowledge" / "raw")
        self.assertEqual(paths.normalized, Path("C:/project") / "knowledge" / "normalized")
        self.assertEqual(paths.notes, Path("C:/project") / "knowledge" / "notes")
        self.assertEqual(paths.graph, Path("C:/project") / "knowledge" / "graph")
        self.assertEqual(paths.index, Path("C:/project") / "knowledge" / "index")

    def test_ensure_directories_creates_beginner_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = BrainPaths(Path(tmp))

            created = paths.ensure_directories()

            self.assertTrue(created)
            for directory in paths.required_directories():
                self.assertTrue(directory.is_dir(), directory)

    def test_default_config_is_beginner_friendly(self) -> None:
        config = BrainConfig.default()

        self.assertEqual("obsidian", config.storage_provider)
        self.assertEqual("docling", config.pdf_converter)
        self.assertEqual("ollama", config.ocr_provider)
        self.assertEqual("deterministic-json", config.graph_provider)
        self.assertEqual("builtin-bm25", config.search_provider)

    def test_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brain.json"
            config = BrainConfig.default()

            save_config(path, config)
            loaded = load_config(path)

            self.assertEqual(config, loaded)


if __name__ == "__main__":
    unittest.main()
