import unittest
from pathlib import Path

from tools.fde_brain.graphify import (
    GraphifyCommand,
    brain_graph_extract,
    graph_json_path,
    mark_graph_fresh,
    mark_graph_stale,
    source_graph_extract,
)


class GraphifyTests(unittest.TestCase):
    def test_brain_graph_extract_uses_fde_brain_input_and_brain_output(self) -> None:
        command = brain_graph_extract(Path("C:/workspace"))

        self.assertEqual(
            GraphifyCommand(
                args=[
                    "graphify",
                    "extract",
                    "C:/workspace/FDE Brain",
                    "--backend",
                    "ollama",
                    "--model",
                    "gemma4:e4b",
                    "--max-concurrency",
                    "1",
                    "--out",
                    "C:/workspace/AI Space/graph/brain",
                ]
            ),
            command,
        )

    def test_source_graph_extract_uses_normalized_input_and_source_output(self) -> None:
        command = source_graph_extract(Path("C:/workspace"))

        self.assertEqual(
            [
                "graphify",
                "extract",
                "C:/workspace/AI Space/normalized",
                "--backend",
                "ollama",
                "--model",
                "gemma4:e4b",
                "--max-concurrency",
                "1",
                "--out",
                "C:/workspace/AI Space/graph/sources",
            ],
            command.args,
        )

    def test_graph_json_path_matches_graphify_output_layout(self) -> None:
        self.assertEqual(
            Path("C:/workspace/AI Space/graph/brain/graphify-out/graph.json"),
            graph_json_path(Path("C:/workspace/AI Space/graph/brain")),
        )

    def test_stale_marker_roundtrip(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            graph_dir = Path(tmp) / "graph"
            mark_graph_stale(graph_dir, "notes changed")
            marker = graph_dir / ".stale"
            self.assertTrue(marker.exists())
            self.assertIn("notes changed", marker.read_text(encoding="utf-8"))

            mark_graph_fresh(graph_dir)
            self.assertFalse(marker.exists())

    def test_command_formats_for_powershell(self) -> None:
        command = GraphifyCommand(["graphify", "query", "hello world", "--budget", "1500"])

        self.assertEqual('graphify query "hello world" --budget 1500', command.to_powershell())

    def test_command_formats_quoted_argument_for_powershell(self) -> None:
        command = GraphifyCommand(["graphify", "query", 'has"quote'])

        self.assertEqual('graphify query "has`"quote"', command.to_powershell())


if __name__ == "__main__":
    unittest.main()
