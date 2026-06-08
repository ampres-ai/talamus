import tempfile
import unittest
from pathlib import Path

from talamus.config import TalamusConfig, load_config, save_config
from talamus.paths import TalamusPaths


class TalamusPathsConfigTests(unittest.TestCase):
    def test_layout_separates_human_notes_from_managed_area(self) -> None:
        paths = TalamusPaths(Path("C:/brain"))

        self.assertEqual(paths.project_root, Path("C:/brain"))
        self.assertEqual(paths.notes, Path("C:/brain") / "notes")
        self.assertEqual(paths.talamus_dir, Path("C:/brain") / ".talamus")
        self.assertEqual(paths.raw, Path("C:/brain") / ".talamus" / "raw")
        self.assertEqual(paths.normalized, Path("C:/brain") / ".talamus" / "normalized")
        self.assertEqual(paths.cache, Path("C:/brain") / ".talamus" / "cache")
        self.assertEqual(paths.notes_cache, Path("C:/brain") / ".talamus" / "cache" / "notes")
        self.assertEqual(paths.graph_file, Path("C:/brain") / ".talamus" / "cache" / "graph.json")
        self.assertEqual(paths.index_file, Path("C:/brain") / ".talamus" / "cache" / "bm25.json")

    def test_ensure_directories_creates_new_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))

            created = paths.ensure_directories()

            self.assertTrue(created)
            for directory in (paths.notes, paths.raw, paths.normalized, paths.notes_cache, paths.logs):
                self.assertTrue(directory.is_dir(), directory)

    def test_default_config_is_beginner_friendly(self) -> None:
        config = TalamusConfig.default()

        self.assertEqual("obsidian", config.storage_provider)
        self.assertEqual("docling", config.pdf_converter)
        self.assertEqual("ollama", config.ocr_provider)
        self.assertEqual("deterministic-json", config.graph_provider)
        self.assertEqual("builtin-bm25", config.search_provider)

    def test_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "talamus.json"
            config = TalamusConfig.default()

            save_config(path, config)
            loaded = load_config(path)

            self.assertEqual(config, loaded)


if __name__ == "__main__":
    unittest.main()
