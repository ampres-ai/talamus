from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.longmemeval.loader import load_dataset
from benchmarks.longmemeval.runner import run_longmemeval

from talamus.routing import StaticRouter
from tests.support import FakeLLMProvider


def _long_content(fact: str) -> str:
    # Session capture intentionally has a substantiality gate; realistic padding
    # keeps this plumbing test on the actual ingest path instead of bypassing it.
    return f"{fact} " + ("This durable project context should be remembered. " * 10)


def _dataset() -> list[dict]:
    return [
        {
            "question_id": "q1",
            "question_type": "single-session-user",
            "question": "Which city hosted the project launch?",
            "answer": "Rome",
            "haystack_sessions": [
                [
                    {"role": "user", "content": _long_content("Where was the launch?")},
                    {
                        "role": "assistant",
                        "content": _long_content("The project launch was hosted in Rome."),
                    },
                ],
                [
                    {"role": "user", "content": _long_content("How are the garden beds?")},
                    {
                        "role": "assistant",
                        "content": _long_content("The garden beds were watered today."),
                    },
                ],
            ],
            "haystack_dates": ["2026-01-10", "2026-01-11"],
            "question_date": "2026-01-12",
            "answer_session_ids": ["s1"],
        },
        {
            "question_id": "q2",
            "question_type": "temporal-reasoning",
            "question": "What beverage does the user prefer?",
            "answer": "tea",
            "haystack_sessions": [
                [
                    {"role": "user", "content": _long_content("What should I drink?")},
                    {
                        "role": "assistant",
                        "content": _long_content("Your preferred beverage is tea."),
                    },
                ],
                [
                    {"role": "user", "content": _long_content("Did I cycle this week?")},
                    {
                        "role": "assistant",
                        "content": _long_content("You completed a bicycle ride on Tuesday."),
                    },
                ],
            ],
            "haystack_dates": ["2026-02-01", "2026-02-02"],
            "question_date": "2026-02-03",
            "answer_session_ids": ["s3"],
        },
    ]


def _note(title: str, retrieval_text: str, summary: str) -> str:
    return json.dumps(
        [
            {
                "title": title,
                "retrieval_text": retrieval_text,
                "summary": summary,
                "supported_claims": [summary],
                "confidence": 0.9,
            }
        ]
    )


class LongMemEvalLoaderTests(unittest.TestCase):
    def test_load_dataset_parses_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "longmemeval_s.json"
            path.write_text(json.dumps(_dataset()), encoding="utf-8")

            loaded = load_dataset(path)

        self.assertEqual(2, len(loaded))
        self.assertEqual("q1", loaded[0]["question_id"])
        self.assertEqual(2, len(loaded[1]["haystack_sessions"]))

    def test_missing_dataset_has_download_instructions(self) -> None:
        missing = Path("definitely-missing-longmemeval.json")

        with self.assertRaises(FileNotFoundError) as raised:
            load_dataset(missing)

        message = str(raised.exception)
        self.assertIn("longmemeval_s.json", message)
        self.assertIn("https://github.com/xiaowu0162/LongMemEval", message)
        self.assertIn(".bench-data/longmemeval/", message)


class LongMemEvalRunnerTests(unittest.TestCase):
    def test_plumbing_with_fake_router_and_judge(self) -> None:
        responses = [
            _note("Project Launch City", "project launch city Rome", "The launch was in Rome."),
            _note("Garden Care", "garden beds water", "The garden beds were watered."),
            "The project launch was in Rome [1].",
            _note("Preferred Beverage", "user preferred beverage tea", "The user prefers tea."),
            _note("Bicycle Ride", "bicycle ride Tuesday", "A bicycle ride happened Tuesday."),
            "The user's preferred beverage is tea [1].",
        ]
        provider = FakeLLMProvider(responses)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_path = root / "longmemeval_s.json"
            out_dir = root / "results"
            dataset_path.write_text(json.dumps(_dataset()), encoding="utf-8")

            # No TALAMUS_BENCH_HEAVY opt-in: injected seams keep this path FAST.
            result = run_longmemeval(
                dataset_path,
                engine="fake",
                limit=2,
                out_dir=out_dir,
                yes=True,
                router_factory=lambda _engine: StaticRouter(provider),
                judge=lambda _question, _gold, _answer: True,
            )

            artifacts = list(out_dir.glob("*-longmemeval.json"))
            self.assertEqual(1, len(artifacts))
            written = json.loads(artifacts[0].read_text(encoding="utf-8"))
            self.assertTrue(artifacts[0].with_suffix(".md").is_file())

        self.assertEqual(1.0, result["accuracy"])
        self.assertEqual(1.0, written["accuracy"])
        self.assertEqual(
            {"single-session-user": 1.0, "temporal-reasoning": 1.0},
            written["accuracy_by_question_type"],
        )
        self.assertEqual(4, written["sessions_ingested"])
        self.assertEqual(0, written["sessions_skipped_by_gate"])
        self.assertEqual(6, len(provider.prompts))


if __name__ == "__main__":
    unittest.main()
