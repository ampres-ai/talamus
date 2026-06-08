import tempfile
import unittest
from pathlib import Path

from talamus.graph import build_graph, load_graph, query_graph, save_graph
from talamus.models import CanonicalNote, Relation, SourceRef


def source_ref() -> SourceRef:
    return SourceRef(
        raw_path="knowledge/raw/pdf/book.pdf",
        normalized_path="knowledge/normalized/pdf/book/sections/001.md",
        locator="pages 1-2",
        source_hash="sha256:abc",
        supported_claims=["RAG retrieves context."],
    )


class TalamusGraphTests(unittest.TestCase):
    def test_build_graph_contains_note_alias_tag_and_source_nodes(self) -> None:
        note = CanonicalNote(
            note_id="rag",
            title="Retrieval-Augmented Generation",
            aliases=["RAG"],
            folder="Retrieval",
            tags=["retrieval"],
            summary="Human summary.",
            retrieval_text="rag external knowledge retrieval",
            body_sections={"core_idea": "RAG retrieves context."},
            proposed_links=[],
            relations=[],
            sources=[source_ref()],
            confidence=0.9,
        )

        graph = build_graph([note])

        self.assertIn("note:rag", graph["nodes"])
        self.assertIn("alias:rag", graph["nodes"])
        self.assertIn("tag:retrieval", graph["nodes"])
        self.assertIn("source:knowledge/normalized/pdf/book/sections/001.md", graph["nodes"])
        self.assertTrue(any(edge["type"] == "has_alias" for edge in graph["edges"]))

    def test_query_graph_routes_by_retrieval_text_and_aliases(self) -> None:
        rag = CanonicalNote.minimal("Retrieval-Augmented Generation", sources=[source_ref()])
        memory = CanonicalNote(
            note_id="agent-memory",
            title="Agent Memory",
            aliases=[],
            folder="Agents",
            tags=["agents"],
            summary="Memory for agents.",
            retrieval_text="agent memory long term context",
            body_sections={"core_idea": "Memory stores context."},
            proposed_links=[],
            relations=[Relation("Agent Memory", "uses", "Retrieval-Augmented Generation", 0.8)],
            sources=[source_ref()],
            confidence=0.8,
        )
        graph = build_graph([rag, memory])

        results = query_graph(graph, "How do agents remember context?", limit=2)

        self.assertEqual("note:agent-memory", results[0]["id"])

    def test_graph_round_trips_to_json(self) -> None:
        note = CanonicalNote.minimal("Retrieval-Augmented Generation", sources=[source_ref()])
        graph = build_graph([note])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.json"
            save_graph(path, graph)
            loaded = load_graph(path)

        self.assertEqual(graph, loaded)


if __name__ == "__main__":
    unittest.main()
