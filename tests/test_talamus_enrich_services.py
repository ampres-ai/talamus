import json
import tempfile
import unittest

from talamus.routing import StaticRouter
from talamus.services.enrich import run_enrich
from talamus.store import load_notes
from tests.support import FakeLLMProvider
from tests.test_talamus_enrich import _brain


class TalamusEnrichServiceTests(unittest.TestCase):
    def test_run_enrich_without_confirmation_does_not_call_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp, ["Allucinazione"])
            llm = FakeLLMProvider([])

            result = run_enrich(tmp, StaticRouter(llm), confirmed=False)

            note = load_notes(paths)[0]

        self.assertTrue(result.success, result.message)
        self.assertEqual("enrich_confirmation_required", result.code)
        self.assertEqual([], llm.prompts)
        self.assertNotIn("~sintomi:", note.retrieval_text)

    def test_run_enrich_confirmed_updates_retrieval_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp, ["Allucinazione"])
            answer = json.dumps(
                [{"id": "allucinazione", "symptoms": "si inventa le cose, makes things up"}]
            )
            llm = FakeLLMProvider([answer])

            result = run_enrich(tmp, StaticRouter(llm), confirmed=True)

            note = load_notes(paths)[0]

        self.assertTrue(result.success, result.message)
        self.assertEqual("enrich_completed", result.code)
        self.assertEqual(1, len(llm.prompts))
        self.assertIn("si inventa le cose", note.retrieval_text)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(1, result.data.enriched)
        self.assertEqual(0, result.data.failed_batches)

    def test_run_enrich_when_done_costs_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _brain(tmp, ["Allucinazione"])
            answer = json.dumps([{"id": "allucinazione", "symptoms": "frasi sintomo"}])
            first = run_enrich(tmp, StaticRouter(FakeLLMProvider([answer])), confirmed=True)
            llm = FakeLLMProvider([])

            second = run_enrich(tmp, StaticRouter(llm), confirmed=True)

        self.assertTrue(first.success, first.message)
        self.assertTrue(second.success, second.message)
        self.assertEqual("enrich_nothing_to_do", second.code)
        self.assertEqual([], llm.prompts)


if __name__ == "__main__":
    unittest.main()
