import json
import tempfile
import unittest
from pathlib import Path

from talamus.ask import answer_question, build_context_bundle
from talamus.graph import build_graph, load_graph
from talamus.ingest import ingest_file
from talamus.models import CanonicalNote, Relation, SourceRef
from talamus.paths import TalamusPaths
from talamus.search import BM25Index
from talamus.store import rebuild_indexes, write_note
from tests.support import FakeLLMProvider


def source_ref() -> SourceRef:
    return SourceRef(
        raw_path="raw/book.pdf",
        normalized_path="normalized/book#1",
        locator="pages 1-2",
        source_hash="sha256:abc",
        supported_claims=["RAG retrieves context."],
    )


def _extract_response() -> str:
    return json.dumps(
        [
            {
                "title": "Retrieval-Augmented Generation",
                "aliases": ["RAG"],
                "tags": ["retrieval"],
                "retrieval_text": "external documents retrieval augmented generation",
                "summary": "RAG connette il modello a fonti esterne.",
                "body_sections": {"core_idea": "RAG recupera contesto."},
                "supported_claims": ["RAG recupera contesto."],
                "confidence": 0.9,
            }
        ]
    )


class TalamusAskTests(unittest.TestCase):
    def test_context_uses_graph_before_bm25(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            note = CanonicalNote(
                note_id="rag",
                title="Retrieval-Augmented Generation",
                aliases=["RAG"],
                folder="Retrieval",
                tags=["retrieval"],
                summary="RAG connette il modello a fonti esterne.",
                retrieval_text="external documents retrieval augmented generation",
                body_sections={"core_idea": "RAG retrieves context."},
                proposed_links=[],
                relations=[],
                sources=[source_ref()],
                confidence=0.9,
            )
            (paths.notes / "Retrieval-Augmented-Generation.md").write_text(
                "# Retrieval-Augmented Generation\n\nRAG retrieves context.", encoding="utf-8"
            )
            graph = build_graph([note])
            search = BM25Index()
            search.add("wrong", "external documents")

            bundle = build_context_bundle(
                paths, graph, search, "How do I use external documents?", limit=1
            )

            self.assertEqual("graph", bundle.items[0]["route"])
            self.assertIn("Retrieval-Augmented-Generation.md", bundle.items[0]["path"])

    def test_answer_question_uses_context_and_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            paths.ensure_directories()
            source = root / "rag.md"
            source.write_text("# RAG\nRAG collega il modello a fonti esterne.", encoding="utf-8")
            ingest_file(paths, source, FakeLLMProvider([_extract_response()]))
            answering = FakeLLMProvider(["RAG collega il modello a fonti esterne [1]."])

            answer = answer_question(paths, "Come collego il modello a fonti esterne?", answering)

            self.assertIn("RAG", answer)
            self.assertIn("Retrieval-Augmented Generation", answering.prompts[0])

    def test_answer_question_without_context_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            from talamus.store import rebuild_indexes

            rebuild_indexes(paths)

            answer = answer_question(paths, "qualcosa", FakeLLMProvider(["non dovrebbe servire"]))

            self.assertIn("nessun contesto", answer.lower())

    def test_retrieval_expands_via_ontology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            alpha = CanonicalNote(
                note_id="alpha",
                title="Alpha",
                aliases=[],
                folder="",
                tags=[],
                summary="a",
                retrieval_text="zebraword unicorno",
                body_sections={"d": "Alpha usa Beta."},
                proposed_links=[],
                relations=[Relation("Alpha", "usa", "Beta", 0.9)],
                sources=[source_ref()],
                confidence=0.9,
            )
            beta = CanonicalNote(
                note_id="beta",
                title="Beta",
                aliases=[],
                folder="",
                tags=[],
                summary="b",
                retrieval_text="parole totalmente diverse",
                body_sections={"d": "Beta."},
                proposed_links=[],
                relations=[],
                sources=[source_ref()],
                confidence=0.9,
            )
            write_note(paths, alpha)
            write_note(paths, beta)
            rebuild_indexes(paths)

            bundle = build_context_bundle(
                paths,
                load_graph(paths.graph_file),
                BM25Index.load(paths.index_file),
                "zebraword",
                limit=5,
            )

            paths_found = [item["path"] for item in bundle.items]
            self.assertTrue(any("Alpha" in p for p in paths_found))
            # Beta non combacia per parole, ma entra perche' collegato ad Alpha nell'ontologia
            self.assertTrue(any("Beta" in p for p in paths_found))


if __name__ == "__main__":
    unittest.main()
