import json
import tempfile
import unittest
from pathlib import Path

from talamus.domains import build_overview
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import rebuild_indexes, write_note
from tests.support import FakeLLMProvider


def _note(title: str) -> CanonicalNote:
    return CanonicalNote.minimal(
        title, sources=[SourceRef("raw", "norm", "loc", "sha256:x", ["claim"])]
    )


class DomainsTests(unittest.TestCase):
    def test_overview_covers_every_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("RAG"))
            write_note(paths, _note("Embedding"))
            rebuild_indexes(paths)
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [{"name": "Retrieval", "description": "d", "members": ["RAG", "Embedding"]}]
                    )
                ]
            )

            domains = build_overview(paths, llm)

            assigned = {member for domain in domains for member in domain["members"]}
            self.assertEqual({"RAG", "Embedding"}, assigned)

    def test_unassigned_notes_fall_back_to_varie(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Alpha"))
            write_note(paths, _note("Beta"))
            rebuild_indexes(paths)

            domains = build_overview(paths, FakeLLMProvider([json.dumps([])]))

            self.assertEqual(1, len(domains))
            self.assertEqual({"Alpha", "Beta"}, set(domains[0]["members"]))

    def test_answer_question_routes_via_overview(self) -> None:
        from talamus.ask import answer_question

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("RAG"))
            rebuild_indexes(paths)
            build_overview(
                paths,
                FakeLLMProvider(
                    [json.dumps([{"name": "Retrieval", "description": "d", "members": ["RAG"]}])]
                ),
            )

            # coda: routing, espansione query (RS3), risposta
            answer = answer_question(
                paths,
                "come funziona?",
                FakeLLMProvider(["Retrieval", "retrieval rag", "Risposta [1]."]),
            )

            self.assertIn("[1]", answer)

    def test_answer_question_expands_query_as_last_resort(self) -> None:
        from talamus.ask import answer_question

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Reranking"))
            rebuild_indexes(paths)
            # no overview built -> routing skipped; the literal question misses; expansion recovers.
            llm = FakeLLMProvider(["reranking", "Risposta [1]."])

            answer = answer_question(paths, "come ordino meglio i risultati?", llm)

            self.assertIn("[1]", answer)


if __name__ == "__main__":
    unittest.main()
