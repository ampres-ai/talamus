import json
import tempfile
import unittest
from pathlib import Path

from talamus.ingest import CHUNK_CHARS, split_chunks
from talamus.paths import TalamusPaths
from talamus.services.ingestion import ingest_raw_text, preview_ingest, run_ingest
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


def _large_markdown(tmp: str, paragraphs: int = 12) -> Path:
    source = Path(tmp) / "libro.md"
    block = "contenuto " * (CHUNK_CHARS // 30)
    source.write_text("\n\n".join(block for _ in range(paragraphs)), encoding="utf-8")
    return source


class TalamusIngestionServiceTests(unittest.TestCase):
    def test_preview_ingest_estimates_large_file_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            source = _large_markdown(tmp)

            result = preview_ingest(tmp, str(source))

            notes = load_notes(paths)

        self.assertTrue(result.success, result.message)
        self.assertEqual("ingest_preview_ready", result.code)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual("file", result.data.target_type)
        self.assertTrue(result.data.requires_confirmation)
        self.assertGreater(result.data.chunks, 3)
        self.assertEqual(result.data.chunks, result.data.est_llm_calls)
        self.assertEqual([], notes)

    def test_run_ingest_large_file_without_confirmation_does_not_call_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            source = _large_markdown(tmp)
            llm = FakeLLMProvider([])

            result = run_ingest(tmp, str(source), llm, confirmed=False)

            notes = load_notes(paths)

        self.assertTrue(result.success, result.message)
        self.assertEqual("ingest_confirmation_required", result.code)
        self.assertEqual([], llm.prompts)
        self.assertEqual([], notes)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertTrue(result.data.requires_confirmation)

    def test_run_ingest_confirmed_large_file_writes_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            source = _large_markdown(tmp, paragraphs=8)
            expected = len(split_chunks(source.read_text(encoding="utf-8")))
            llm = FakeLLMProvider([_note_json(f"Nota {i}") for i in range(expected)])

            result = run_ingest(tmp, str(source), llm, confirmed=True)

            notes = load_notes(paths)

        self.assertTrue(result.success, result.message)
        self.assertEqual("ingest_completed", result.code)
        self.assertEqual(expected, len(llm.prompts))
        self.assertEqual(expected, len(notes))
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(expected, result.data.notes_written)
        self.assertEqual(expected, result.data.chunks)
        self.assertEqual("completed", result.data.state)

    def test_ingest_raw_text_writes_a_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            llm = FakeLLMProvider([_note_json("Insight")])

            result = ingest_raw_text(tmp, "A short insight worth keeping.", llm)

            notes = load_notes(paths)

        self.assertTrue(result.success, result.message)
        self.assertEqual("text_ingested", result.code)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(1, result.data.notes_written)
        self.assertEqual(1, len(notes))


if __name__ == "__main__":
    unittest.main()
