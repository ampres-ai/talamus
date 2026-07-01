import json
import unittest

from talamus.extract import extract_notes
from talamus.normalize import normalize_text
from talamus.routing import StaticRouter, TaskClass
from tests.support import FakeLLMProvider


class ExtractTests(unittest.TestCase):
    def _package(self):
        return normalize_text(
            "knowledge/raw/rag.md", "# RAG\nRAG collega il modello a fonti esterne."
        )

    def test_extracts_canonical_note_with_provenance(self) -> None:
        llm_json = json.dumps(
            [
                {
                    "title": "Retrieval-Augmented Generation",
                    "aliases": ["RAG"],
                    "tags": ["retrieval"],
                    "summary": "RAG collega il modello a fonti esterne.",
                    "retrieval_text": "rag retrieval fonti esterne",
                    "body_sections": {"core_idea": "Recupera contesto prima di generare."},
                    "relations": [],
                    "supported_claims": ["RAG collega il modello a fonti esterne."],
                    "confidence": 0.9,
                }
            ]
        )
        llm = FakeLLMProvider([llm_json])

        notes = extract_notes(self._package(), StaticRouter(llm))

        self.assertEqual(1, len(notes))
        note = notes[0]
        self.assertEqual("Retrieval-Augmented Generation", note.title)
        self.assertEqual(1, len(note.sources))
        self.assertEqual("knowledge/raw/rag.md", note.sources[0].raw_path)
        self.assertEqual([], note.validation_errors())

    def test_ignores_text_around_json_array(self) -> None:
        llm = FakeLLMProvider(['Ecco le note:\n[{"title":"X","supported_claims":["y"]}]\nfine'])

        notes = extract_notes(self._package(), StaticRouter(llm))

        self.assertEqual("X", notes[0].title)

    def test_extract_notes_resolves_the_extraction_task_from_the_router(self) -> None:
        requested: list[TaskClass] = []

        class RecordingRouter:
            def for_task(self, task: TaskClass):
                requested.append(task)
                return FakeLLMProvider(['[{"title": "X", "summary": "s"}]'])

        extract_notes(self._package(), RecordingRouter())
        self.assertEqual(requested, [TaskClass.EXTRACTION])


if __name__ == "__main__":
    unittest.main()
