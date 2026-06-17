import unittest

from benchmarks.ask_eval.judges import correctness_verdict, faithfulness_verdict, is_refusal
from benchmarks.ask_eval.pipeline import evaluate_answers, generate_answer
from benchmarks.shootout.corpora.judged import JudgedCorpus
from benchmarks.shootout.systems.fake import FakeSystem


class _ScriptedLLM:
    """Returns a fixed verdict/answer regardless of prompt (deterministic judge)."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._reply


class JudgeTests(unittest.TestCase):
    def test_refusal_detection(self) -> None:
        self.assertTrue(is_refusal("Il contesto non contiene informazioni sufficienti."))
        self.assertTrue(is_refusal("I don't know based on the sources."))
        self.assertFalse(is_refusal("La quantizzazione riduce i bit del modello [1]."))

    def test_faithfulness_parses_verdict(self) -> None:
        self.assertTrue(faithfulness_verdict("a [1]", "ctx", _ScriptedLLM("GROUNDED")))
        self.assertFalse(faithfulness_verdict("a [1]", "ctx", _ScriptedLLM("HALLUCINATED")))

    def test_correctness_parses_grade(self) -> None:
        self.assertEqual(correctness_verdict("a", "q", "ref", _ScriptedLLM("CORRECT")), "correct")
        self.assertEqual(correctness_verdict("a", "q", "ref", _ScriptedLLM("PARTIAL")), "partial")
        self.assertEqual(correctness_verdict("a", "q", "ref", _ScriptedLLM("WRONG")), "wrong")

    def test_generate_answer_refuses_without_context(self) -> None:
        out = generate_answer("q", [], _ScriptedLLM("unused"))
        self.assertTrue(is_refusal(out))


class EvaluateAnswersTests(unittest.TestCase):
    def _corpus(self) -> JudgedCorpus:
        return JudgedCorpus(
            docs=[
                ("d1", "Cats", "the cat sat on the mat"),
                ("d2", "Dogs", "the dog ran in the park"),
            ],
            queries={"q1": "cat"},
            qrels={"q1": {"d1": 1}},
        )

    def test_end_to_end_with_fakes(self) -> None:
        result = evaluate_answers(
            FakeSystem(),
            self._corpus(),
            gen_llm=_ScriptedLLM("the cat sat [1]"),
            judge_llm=_ScriptedLLM("GROUNDED CORRECT"),
            k=2,
            negatives=[{"question": "kubernetes config"}],
        )
        self.assertEqual(result["n"], 1)
        self.assertEqual(result["context_hit"], 1.0)  # d1 retrieved for "cat"
        self.assertEqual(result["faithfulness"], 1.0)
        self.assertEqual(result["answer_correctness"], 1.0)
        # the negative query matches nothing -> empty context -> refusal
        self.assertEqual(result["honest_refusal"], 1.0)


if __name__ == "__main__":
    unittest.main()
