import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fde_brain.ask import build_context_bundle, answer_question
from tools.fde_brain.paths import WorkspacePaths


NOTE = """---
type: concept
status: evergreen
aliases:
  - Retrieval Augmented Generation
tags:
  - ai-engineering
sources:
  - raw_path: AI Space/raw/markdown/rag.md
    normalized_path: AI Space/normalized/markdown/rag/sections/001-rag.md
    locator: markdown
    source_hash: sha256:rag
    supported_claims:
      - RAG combines retrieval with generation.
created: 2026-05-26T00:00:00+00:00
updated: 2026-05-26T00:00:00+00:00
---

# Retrieval Augmented Generation

## Summary

RAG combines retrieval with generation to answer from external knowledge.

## Core Idea

Retrieve relevant context, then generate from that context.

## Practical Use

Use RAG when knowledge changes faster than model weights.

## Related
"""


class AskTests(unittest.TestCase):
    def test_context_bundle_reads_real_markdown_without_graph_output_as_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            (paths.fde_brain / "Retrieval-Augmented-Generation.md").write_text(NOTE, encoding="utf-8")

            bundle = build_context_bundle(paths, "When should I use RAG?", graph_runner=None)

        self.assertTrue(bundle.items)
        self.assertEqual("brain", bundle.items[0].layer)
        self.assertIn("FDE Brain/Retrieval-Augmented-Generation.md", bundle.items[0].path)
        self.assertIn("RAG combines retrieval", bundle.items[0].content)
        self.assertTrue(bundle.citations)

    def test_context_bundle_prioritizes_graphify_routed_markdown_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            routed = paths.fde_brain / "Graph-Routed.md"
            routed.write_text("# Graph Routed\n\nSelected only by Graphify.", encoding="utf-8")
            (paths.fde_brain / "Keyword-Hit.md").write_text("# RAG\n\nRAG RAG RAG.", encoding="utf-8")
            graph_json = paths.brain_graph / "graphify-out" / "graph.json"
            graph_json.parent.mkdir(parents=True, exist_ok=True)
            graph_json.write_text("{}", encoding="utf-8")

            def runner(_args: list[str]) -> str:
                return "Candidate: FDE Brain/Graph-Routed.md"

            bundle = build_context_bundle(paths, "When should I use RAG?", graph_runner=runner)

        self.assertTrue(bundle.items)
        self.assertEqual("FDE Brain/Graph-Routed.md", bundle.items[0].path)

    def test_context_bundle_ignores_stale_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            routed = paths.fde_brain / "Graph-Routed.md"
            routed.write_text("# Graph Routed\n\nSelected only by Graphify.", encoding="utf-8")
            keyword = paths.fde_brain / "Keyword-Hit.md"
            keyword.write_text("# RAG\n\nRAG RAG RAG.", encoding="utf-8")
            graph_json = paths.brain_graph / "graphify-out" / "graph.json"
            graph_json.parent.mkdir(parents=True, exist_ok=True)
            graph_json.write_text("{}", encoding="utf-8")
            (paths.brain_graph / ".stale").write_text("stale", encoding="utf-8")

            def runner(_args: list[str]) -> str:
                return "Candidate: FDE Brain/Graph-Routed.md"

            bundle = build_context_bundle(paths, "When should I use RAG?", graph_runner=runner)

        self.assertTrue(bundle.items)
        self.assertEqual("FDE Brain/Keyword-Hit.md", bundle.items[0].path)

    @patch("tools.fde_brain.ask.ollama.chat")
    def test_answer_question_with_gemma_reports_model_and_uses_citations(self, chat_mock) -> None:
        chat_mock.return_value = {"message": {"content": "Use RAG when knowledge changes. [1]"}}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            (paths.fde_brain / "Retrieval-Augmented-Generation.md").write_text(NOTE, encoding="utf-8")

            answer = answer_question(paths, "When should I use RAG?", model="gemma", read_only=True)

        self.assertEqual("gemma", answer.model)
        self.assertIn("Use RAG", answer.text)
        self.assertTrue(answer.citations)

    @patch("tools.fde_brain.ask.ollama.chat")
    def test_answer_promotes_source_fallback_when_not_read_only(self, chat_mock) -> None:
        chat_mock.side_effect = [
            {"message": {"content": "Answer from source. [1]"}},
            {
                "message": {
                    "content": (
                        '{"notes":[{"title":"Source Pattern","type":"pattern",'
                        '"aliases":["Source Pattern"],"summary":"Summary.",'
                        '"core_idea":"Core.","practical_use":"Use.",'
                        '"related":[],"tags":["ai-engineering"],"confidence":0.9,'
                        '"supported_claims":["Claim."]}]}'
                    )
                }
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            section = paths.normalized_for("markdown") / "source" / "sections" / "001-source.md"
            section.parent.mkdir(parents=True, exist_ok=True)
            section.write_text(
                "---\nsource-path: AI Space/raw/markdown/source.md\nsource-hash: sha256:x\n"
                "source-location: markdown\n---\n\n# Source\n\nRareterm source fallback content.",
                encoding="utf-8",
            )

            answer = answer_question(paths, "rareterm?", model="gemma", read_only=False, graph_runner=None)

            promoted = paths.fde_brain / "Source-Pattern.md"
            self.assertTrue(promoted.exists())
            self.assertIn("Source Pattern", promoted.read_text(encoding="utf-8"))
            self.assertIn("FDE Brain/Source-Pattern.md", answer.promoted_to)


if __name__ == "__main__":
    unittest.main()
