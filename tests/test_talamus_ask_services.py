import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from talamus.demo import create_demo_brain
from talamus.errors import EngineNotFound
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.services.ask import ask_brain


class _FakeLLM:
    """A deterministic provider: the sentinel won't match any domain id/name, so
    routing falls through to the index path and answer_from_items returns it."""

    label = "Fake Engine"

    def complete(self, prompt: str) -> str:
        return "QQZ synthesized answer citing [1]."


class AskServiceTests(unittest.TestCase):
    def test_empty_question_is_rejected_without_touching_an_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = ask_brain(Path(tmp), "   ")
        self.assertFalse(result.success)
        self.assertEqual("ask_empty", result.code)

    def test_injected_engine_produces_a_cited_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            result = ask_brain(
                root, "what is retrieval augmented generation?", router=StaticRouter(_FakeLLM())
            )
        self.assertTrue(result.success)
        self.assertEqual("ask_answered", result.code)
        self.assertIsNotNone(result.data)
        self.assertTrue(result.data.answered)
        self.assertIn("QQZ synthesized answer", result.data.answer)
        self.assertEqual("Fake Engine", result.data.engine)
        self.assertTrue(result.data.sources)

    def test_answer_exposes_route_and_token_cost(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            result = ask_brain(root, "how does reranking work?", router=StaticRouter(_FakeLLM()))
        self.assertTrue(result.success)
        assert result.data is not None
        self.assertTrue(result.data.answered)
        self.assertGreater(result.data.context_tokens, 0)  # the token cost is surfaced
        self.assertTrue(result.data.route)

    def test_as_of_answers_from_the_past_and_marks_the_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            result = ask_brain(
                root,
                "what is retrieval augmented generation?",
                router=StaticRouter(_FakeLLM()),
                as_of="2030",  # far future: every demo note exists by then
            )
        self.assertTrue(result.success, result.message)
        assert result.data is not None
        self.assertTrue(result.data.answered)
        self.assertEqual("as-of", result.data.route)
        self.assertEqual("2030", result.data.as_of)

    def test_as_of_before_any_note_reports_empty_past(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            result = ask_brain(
                root,
                "what is retrieval augmented generation?",
                router=StaticRouter(_FakeLLM()),
                as_of="1990",  # before the brain existed
            )
        self.assertTrue(result.success)
        assert result.data is not None
        self.assertFalse(result.data.answered)
        self.assertIn("1990", result.data.notice)

    def test_no_engine_degrades_to_relevant_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_demo_brain(TalamusPaths(root))
            # the engine is now built LAZILY inside the router: patch the name
            # EngineRouter.for_task actually calls (bound into talamus.routing)
            with patch(
                "talamus.routing.build_provider_for_task",
                side_effect=EngineNotFound("none"),
            ):
                result = ask_brain(root, "how does reranking work?")
        self.assertTrue(result.success)
        self.assertEqual("ask_no_engine", result.code)
        self.assertIsNotNone(result.data)
        self.assertFalse(result.data.answered)
        self.assertEqual("", result.data.answer)
        self.assertTrue(result.data.sources)  # retrieval still found notes
        self.assertIn("No engine connected", result.data.notice)


if __name__ == "__main__":
    unittest.main()
