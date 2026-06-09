import tempfile
import unittest
from pathlib import Path

from talamus.cli import main
from talamus.demo import create_demo_brain
from talamus.graph import load_graph
from talamus.paths import TalamusPaths
from talamus.recall import search_notes


class DemoBrainTests(unittest.TestCase):
    def test_demo_brain_is_searchable_and_crosslinked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            count = create_demo_brain(paths)

            self.assertEqual(3, count)
            self.assertEqual(3, len(list(paths.notes.glob("*.md"))))
            self.assertTrue(paths.graph_file.is_file())
            self.assertTrue(paths.index_file.is_file())

            results = search_notes(paths, "reranking")
            self.assertTrue(any(r["title"] == "Reranking" for r in results))

            # demo notes are connected by typed relations in the graph index
            graph = load_graph(paths.graph_file)
            typed = [e for e in graph["edges"] if e.get("type") in ("uses", "part-of")]
            self.assertTrue(typed)

    def test_demo_command_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(0, main(["demo", "--root", tmp]))


if __name__ == "__main__":
    unittest.main()
