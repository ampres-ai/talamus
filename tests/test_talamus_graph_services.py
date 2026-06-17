import json
import tempfile
import unittest
from pathlib import Path

from talamus.demo import create_demo_brain
from talamus.paths import TalamusPaths
from talamus.services.graph import get_graph_snapshot, list_graph_neighbors


class TalamusGraphServiceTests(unittest.TestCase):
    def test_graph_snapshot_loads_typed_nodes_and_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            create_demo_brain(paths)

            result = get_graph_snapshot(tmp)

        self.assertTrue(result.success, result.message)
        snapshot = result.data
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertGreater(snapshot.node_count, 0)
        self.assertGreater(snapshot.edge_count, 0)
        labels = {node.label for node in snapshot.nodes}
        self.assertIn("Embedding", labels)
        embedding = next(
            node for node in snapshot.nodes if node.label == "Embedding" and node.kind == "note"
        )
        self.assertEqual("note", embedding.kind)
        self.assertIn("summary", embedding.data)
        self.assertTrue(all(edge.source and edge.target and edge.type for edge in snapshot.edges))

    def test_graph_neighbors_loads_typed_relations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            create_demo_brain(paths)

            result = list_graph_neighbors(tmp, "Embedding")

        self.assertTrue(result.success, result.message)
        neighbors = result.data
        self.assertIsNotNone(neighbors)
        assert neighbors is not None
        titles = {item.title for item in neighbors}
        relations = {item.relation for item in neighbors}
        directions = {item.direction for item in neighbors}
        self.assertIn("Retrieval-Augmented Generation", titles)
        self.assertIn("uses", relations)
        self.assertIn("part-of", relations)
        self.assertEqual({"in", "out"}, directions)

    def test_missing_graph_cache_returns_empty_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()

            result = get_graph_snapshot(tmp)

        self.assertTrue(result.success, result.message)
        self.assertEqual("graph_snapshot_empty", result.code)
        snapshot = result.data
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(0, snapshot.node_count)
        self.assertEqual(0, snapshot.edge_count)

    def test_malformed_graph_cache_fails_instead_of_looking_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            paths.graph_file.write_text(
                json.dumps({"nodes": {"broken": "not an object"}, "edges": []}),
                encoding="utf-8",
            )

            result = get_graph_snapshot(tmp)

        self.assertFalse(result.success)
        self.assertEqual("graph_service_error", result.code)


if __name__ == "__main__":
    unittest.main()
