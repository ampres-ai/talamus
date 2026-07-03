"""Chunked big-document ingest: deterministic split, cost preview, resumable job.

This is the path a 500-page book takes: one extraction call per chunk, progress
persisted after each, engine outages pause (not burn) the job, and the CLI
refuses to start a multi-chunk ingest without an explicit --yes after the
cost estimate (PRD rule: no expensive LLM runs without dry-run + consent)."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from talamus.errors import EngineFailed
from talamus.ingest import (
    CHUNK_CHARS,
    CHUNK_OVERLAP,
    estimate_chunks,
    ingest_file,
    ingest_large,
    split_chunks,
)
from talamus.jobs import JobStore
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.store import load_notes
from tests.support import FakeLLMProvider


def _note_json(title: str) -> str:
    return json.dumps(
        [
            {
                "title": title,
                "retrieval_text": title.lower(),
                "summary": f"{title}.",
                "supported_claims": ["x"],
                "confidence": 0.9,
            }
        ]
    )


def _brain(tmp: str) -> TalamusPaths:
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    return paths


class SplitChunksTests(unittest.TestCase):
    def test_small_text_is_one_chunk(self) -> None:
        self.assertEqual(split_chunks("breve"), ["breve"])

    def test_split_respects_limit_and_keeps_all_content(self) -> None:
        paragraphs = [f"Paragrafo {i}. " + "parola " * 200 for i in range(40)]
        text = "\n\n".join(paragraphs)
        chunks = split_chunks(text, limit=5_000)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 5_000 + CHUNK_OVERLAP + 2)
        merged = " ".join(chunks)
        for i in range(40):
            self.assertIn(f"Paragrafo {i}.", merged)

    def test_split_is_deterministic(self) -> None:
        text = "\n\n".join("blocco " * 300 for _ in range(20))
        self.assertEqual(split_chunks(text, limit=4_000), split_chunks(text, limit=4_000))

    def test_giant_single_paragraph_is_hard_split(self) -> None:
        text = "x" * 50_000  # no paragraph boundaries at all
        chunks = split_chunks(text, limit=20_000, overlap=0)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(sum(len(c) for c in chunks), 50_000)

    def test_overlap_keeps_boundary_concept_whole(self) -> None:
        setup = "Setup. " + "a" * 1_900
        concept = "The boundary concept says alpha beta gamma stay together."
        explanation = "Explanation. " + "b" * 500
        after = "After. " + "c" * 1_900
        text = "\n\n".join([setup, concept, explanation, after])
        no_overlap = split_chunks(text, limit=2_500, overlap=0)
        chunks = split_chunks(text, limit=2_500, overlap=700)
        self.assertGreater(len(chunks), 1)
        self.assertFalse(any(concept in chunk for chunk in no_overlap[1:]))
        self.assertTrue(any(concept in chunk for chunk in chunks[1:]))

    def test_overlap_zero_matches_historical_output(self) -> None:
        text = "\n\n".join(
            [
                "P0 " + "a" * 20,
                "P1 " + "b" * 20,
                "P2 " + "c" * 20,
                "P3 " + "d" * 20,
                "P4 " + "e" * 20,
            ]
        )
        self.assertEqual(
            split_chunks(text, limit=60, overlap=0),
            [
                "P0 " + "a" * 20 + "\n\n" + "P1 " + "b" * 20,
                "P2 " + "c" * 20 + "\n\n" + "P3 " + "d" * 20,
                "P4 " + "e" * 20,
            ],
        )

    def test_split_is_deterministic_with_overlap(self) -> None:
        text = "\n\n".join(f"blocco {i}. " + "x" * 500 for i in range(16))
        self.assertEqual(
            split_chunks(text, limit=1_800, overlap=650),
            split_chunks(text, limit=1_800, overlap=650),
        )

    def test_overlap_does_not_change_chunk_count(self) -> None:
        text = "\n\n".join(f"paragrafo {i}. " + "x" * 700 for i in range(20))
        self.assertEqual(
            len(split_chunks(text, limit=2_000, overlap=0)),
            len(split_chunks(text, limit=2_000, overlap=500)),
        )

    def test_giant_single_paragraph_is_hard_split_with_overlap(self) -> None:
        text = "x" * 50_000
        chunks = split_chunks(text, limit=20_000, overlap=1_000)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(len(split_chunks(text, limit=20_000, overlap=0)), len(chunks))
        self.assertTrue(all(chunk for chunk in chunks))


class EstimateTests(unittest.TestCase):
    def test_estimate_counts_chunks_without_llm_or_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            book = Path(tmp) / "libro.md"
            book.write_text("\n\n".join("riga " * 500 for _ in range(30)), encoding="utf-8")
            estimate = estimate_chunks(paths, book)
            self.assertGreater(estimate["chunks"], 1)
            self.assertEqual(estimate["chunks"], estimate["est_llm_calls"])
            self.assertEqual(list(paths.raw.glob("*")), [])  # preview writes nothing


class ChunkedIngestTests(unittest.TestCase):
    def _book(self, tmp: str, paragraphs: int = 12) -> Path:
        book = Path(tmp) / "libro.md"
        block = "contenuto " * (CHUNK_CHARS // 30)
        book.write_text("\n\n".join(block for _ in range(paragraphs)), encoding="utf-8")
        return book

    def test_big_file_routes_to_resumable_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            book = self._book(tmp)
            expected = len(split_chunks(book.read_text(encoding="utf-8")))
            llm = FakeLLMProvider([_note_json(f"Nota {i}") for i in range(expected)])
            result = ingest_file(paths, book, StaticRouter(llm))
            self.assertEqual(result["chunks"], expected)
            self.assertEqual(result["state"], "completed")
            self.assertEqual(result["notes_written"], expected)
            self.assertEqual(len(llm.prompts), expected)  # one extraction call per chunk
            self.assertEqual(len(load_notes(paths)), expected)
            record = JobStore(paths).load(result["job_id"])
            self.assertEqual(record.state, "completed")
            self.assertEqual(record.result["chunks"], expected)

    def test_engine_outage_pauses_job_and_resume_skips_done_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            book = self._book(tmp)
            chunks = split_chunks(book.read_text(encoding="utf-8"))

            class FlakyProvider:
                """Works for 2 chunks, then the engine 'goes down'."""

                def __init__(self) -> None:
                    self.calls = 0

                def complete(self, prompt: str) -> str:
                    self.calls += 1
                    if self.calls > 2:
                        raise EngineFailed("engine down")
                    return _note_json(f"Nota {self.calls}")

            with self.assertRaises(EngineFailed):
                ingest_file(paths, book, StaticRouter(FlakyProvider()))
            store = JobStore(paths)
            failed = [r for r in store.list() if r.kind == "ingest"][0]
            self.assertEqual(failed.state, "failed")
            self.assertEqual(failed.progress["done"], 2)  # progress survived the crash

            resumed = FakeLLMProvider([_note_json(f"Ripresa {i}") for i in range(len(chunks))])
            report = ingest_large(paths, book, StaticRouter(resumed), job_record=failed)
            self.assertEqual(report["state"], "completed")
            self.assertEqual(len(resumed.prompts), len(chunks) - 2)  # done chunks NOT redone

    def test_bad_chunk_content_is_retried_once_then_recorded(self) -> None:
        """Real-world case from the AI Engineering book run: flash models emit
        malformed JSON ~3% of the time; one retry almost always rescues it."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            book = self._book(tmp)
            expected = len(split_chunks(book.read_text(encoding="utf-8")))
            # chunk 1: bad first answer, good on retry -> rescued, NOT failed
            responses = [_note_json("Nota 0"), "NON-JSON", _note_json("Riprovata")]
            responses += [_note_json(f"Nota {i}") for i in range(2, expected)]
            result = ingest_file(paths, book, StaticRouter(FakeLLMProvider(responses)))
            self.assertEqual(result["state"], "completed")
            self.assertEqual(result["failed"], [])
            self.assertEqual(result["notes_written"], expected)

    def test_chunk_failing_twice_is_recorded_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            book = self._book(tmp)
            expected = len(split_chunks(book.read_text(encoding="utf-8")))
            # chunk 1: bad twice (first try + retry) -> recorded, book continues
            responses = [_note_json("Nota 0"), "NON-JSON", "ANCORA-NON-JSON"]
            responses += [_note_json(f"Nota {i}") for i in range(2, expected)]
            result = ingest_file(paths, book, StaticRouter(FakeLLMProvider(responses)))
            self.assertEqual(result["state"], "completed")
            self.assertEqual(len(result["failed"]), 1)
            self.assertEqual(result["failed"][0]["chunk"], 1)
            self.assertEqual(result["notes_written"], expected - 1)

    def test_chunk_files_are_always_markdown(self) -> None:
        """Chunks hold extracted text: never the source binary extension (a
        .pdf-named text chunk would break verify, which dispatches on suffix)."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            book = self._book(tmp)
            book_pdfish = book.rename(Path(tmp) / "libro.txt")
            expected = len(split_chunks(book_pdfish.read_text(encoding="utf-8")))
            llm = FakeLLMProvider([_note_json(f"Nota {i}") for i in range(expected)])
            ingest_file(paths, book_pdfish, StaticRouter(llm))
            chunk_files = sorted(paths.raw.glob("libro-c*"))
            self.assertEqual(len(chunk_files), expected)
            self.assertTrue(all(f.suffix == ".md" for f in chunk_files))


class CliConsentGateTests(unittest.TestCase):
    def test_multi_chunk_ingest_without_yes_prints_estimate_and_stops(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            book = Path(tmp) / "libro.md"
            block = "contenuto " * (CHUNK_CHARS // 30)
            book.write_text("\n\n".join(block for _ in range(12)), encoding="utf-8")
            llm = FakeLLMProvider([])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["ingest", str(book), "--root", tmp], llm=llm)
            self.assertEqual(0, code)
            self.assertEqual(llm.prompts, [])  # not a single LLM call without consent
            self.assertIn("--yes", out.getvalue())
            self.assertIn("chunk", out.getvalue())
            self.assertEqual(len(load_notes(paths)), 0)

    def test_with_yes_the_job_runs(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            book = Path(tmp) / "libro.md"
            block = "contenuto " * (CHUNK_CHARS // 30)
            book.write_text("\n\n".join(block for _ in range(8)), encoding="utf-8")
            expected = len(split_chunks(book.read_text(encoding="utf-8")))
            llm = FakeLLMProvider([_note_json(f"Nota {i}") for i in range(expected)])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["ingest", str(book), "--yes", "--root", tmp], llm=llm)
            self.assertEqual(0, code)
            self.assertEqual(len(load_notes(paths)), expected)
            self.assertIn("chunk", out.getvalue())


if __name__ == "__main__":
    unittest.main()
