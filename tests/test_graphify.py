import unittest
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch

from tools.fde_brain.graphify import (
    GraphifyCommand,
    brain_graph_extract,
    graph_json_path,
    mark_graph_fresh,
    mark_graph_stale,
    run_graphify_command,
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
                    "--token-budget",
                    "12000",
                    "--api-timeout",
                    "1800",
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
                "--token-budget",
                "12000",
                "--api-timeout",
                "1800",
                "--out",
                "C:/workspace/AI Space/graph/sources",
            ],
            command.args,
        )

    def test_extract_command_accepts_local_runtime_overrides(self) -> None:
        command = brain_graph_extract(
            Path("C:/workspace"),
            token_budget=8000,
            api_timeout=900,
        )

        self.assertIn("--token-budget", command.args)
        self.assertIn("8000", command.args)
        self.assertIn("--api-timeout", command.args)
        self.assertIn("900", command.args)

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

    @patch("tools.fde_brain.graphify.subprocess.run")
    def test_semantic_chunk_failures_keep_graph_stale_even_with_graph_json(self, run_mock) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            graph_dir = Path(tmp) / "graph"
            graph_json_path(graph_dir).parent.mkdir(parents=True, exist_ok=True)
            graph_json_path(graph_dir).write_text("{}", encoding="utf-8")
            run_mock.return_value = CompletedProcess(
                args=["graphify"],
                returncode=0,
                stdout="wrote graph.json",
                stderr="WARNING: 5/5 semantic chunk(s) failed",
            )

            result = run_graphify_command(GraphifyCommand(["graphify"]), graph_dir)

            self.assertEqual(0, result.returncode)
            marker = graph_dir / ".stale"
            self.assertTrue(marker.exists())
            self.assertIn("semantic", marker.read_text(encoding="utf-8"))

    @patch("tools.fde_brain.graphify.subprocess.run")
    def test_run_sets_graphify_out_to_managed_graph_dir(self, run_mock) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            graph_dir = Path(tmp) / "graph"
            graph_json_path(graph_dir).parent.mkdir(parents=True, exist_ok=True)
            graph_json_path(graph_dir).write_text("{}", encoding="utf-8")
            run_mock.return_value = CompletedProcess(args=["graphify"], returncode=0, stdout="", stderr="")

            run_graphify_command(GraphifyCommand(["graphify"]), graph_dir)

            env = run_mock.call_args.kwargs["env"]
            self.assertEqual(str((graph_dir / "graphify-out").resolve()), env["GRAPHIFY_OUT"])

    @patch("tools.fde_brain.graphify.subprocess.run")
    def test_timeout_keeps_graph_stale(self, run_mock) -> None:
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            graph_dir = Path(tmp) / "graph"
            run_mock.side_effect = subprocess.TimeoutExpired(["graphify"], timeout=12, stderr="slow model")

            result = run_graphify_command(GraphifyCommand(["graphify"]), graph_dir, timeout_sec=12)

            self.assertEqual(124, result.returncode)
            marker = graph_dir / ".stale"
            self.assertTrue(marker.exists())
            self.assertIn("timed out", marker.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
