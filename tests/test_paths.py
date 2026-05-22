import tempfile
import unittest
from pathlib import Path

from tools.fde_brain.paths import WorkspacePaths


class WorkspacePathsTests(unittest.TestCase):
    def test_paths_are_derived_from_root(self) -> None:
        root = Path("C:/workspace")
        paths = WorkspacePaths(root)

        self.assertEqual(paths.ai_space, root / "AI Space")
        self.assertEqual(paths.fde_brain, root / "FDE Brain")
        self.assertEqual(paths.pending, root / "AI Space" / "pending")
        self.assertEqual(paths.raw, root / "AI Space" / "raw")
        self.assertEqual(paths.normalized, root / "AI Space" / "normalized")
        self.assertEqual(paths.brain_graph, root / "AI Space" / "graph" / "brain")
        self.assertEqual(paths.source_graph, root / "AI Space" / "graph" / "sources")
        self.assertEqual(paths.agent_protocol, root / "AI Space" / "system" / "AGENT_PROTOCOL.md")

    def test_required_directories_lists_operational_folders(self) -> None:
        paths = WorkspacePaths(Path("C:/workspace"))

        required = {p.as_posix() for p in paths.required_directories()}

        self.assertIn("C:/workspace/AI Space/pending", required)
        self.assertIn("C:/workspace/AI Space/logs/runs", required)
        self.assertIn("C:/workspace/AI Space/review/conflicts", required)
        self.assertIn("C:/workspace/AI Space/failed/technical-failures", required)
        self.assertIn("C:/workspace/FDE Brain", required)

    def test_log_subpath_helpers(self) -> None:
        root = Path("C:/workspace")
        paths = WorkspacePaths(root)

        self.assertEqual(paths.logs_runs, root / "AI Space" / "logs" / "runs")
        self.assertEqual(paths.logs_decisions, root / "AI Space" / "logs" / "decisions")
        self.assertEqual(paths.logs_errors, root / "AI Space" / "logs" / "errors")
        self.assertEqual(paths.logs_promotions, root / "AI Space" / "logs" / "promotions")

    def test_category_subpath_helpers(self) -> None:
        root = Path("C:/workspace")
        paths = WorkspacePaths(root)

        self.assertEqual(paths.raw_for("pdf"), root / "AI Space" / "raw" / "pdf")
        self.assertEqual(paths.normalized_for("image"), root / "AI Space" / "normalized" / "image")
        self.assertEqual(paths.registry_path, root / "AI Space" / "normalized" / "registry.json")

    def test_ensure_directories_creates_all_required_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)

            created = paths.ensure_directories()

            self.assertGreater(len(created), 0)
            for directory in paths.required_directories():
                self.assertTrue(directory.exists(), f"missing {directory}")


if __name__ == "__main__":
    unittest.main()
