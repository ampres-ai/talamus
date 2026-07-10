"""Symptom enrichment: batches, idempotency, CLI consent.

The vague gap is purely semantic (measured: PRF and triangulation rejected); the
bridge is built ONCE by writing into retrieval_text the phrasings a user would
pose the problem with. Kept separate from extraction: loading the ingest prompt
was measured and costs coverage on lite models."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from talamus.enrich import BATCH_SIZE, enrich_estimate, enrich_notes
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.store import load_notes, rebuild_indexes, write_note
from tests.support import FakeLLMProvider


def _note(title: str, summary: str) -> CanonicalNote:
    src = SourceRef("raw/a.md", "raw/a.md#1", "s", "sha256:x", ["c"])
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=[],
        folder="",
        tags=[],
        summary=summary,
        retrieval_text=f"{title} {summary}",
        body_sections={"definizione": summary},
        proposed_links=[],
        relations=[],
        sources=[src],
        confidence=0.9,
    )


def _brain(tmp: str, titles: list[str]) -> TalamusPaths:
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    for title in titles:
        write_note(paths, _note(title, f"Concetto {title}."))
    rebuild_indexes(paths)
    return paths


class EnrichTests(unittest.TestCase):
    def test_symptoms_land_in_retrieval_text_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp, ["Allucinazione"])
            answer = json.dumps(
                [{"id": "allucinazione", "symptoms": "si inventa le cose, makes things up"}]
            )
            report = enrich_notes(paths, StaticRouter(FakeLLMProvider([answer])))
            self.assertEqual(report["enriched"], 1)
            note = load_notes(paths)[0]
            self.assertIn("si inventa le cose", note.retrieval_text)
            # e la query vaga ora trova la nota via indice di produzione
            from talamus.indexes import search_index

            hits = search_index(paths, "il modello si inventa le cose", limit=3)
            self.assertEqual(hits[0]["title"], "Allucinazione")

    def test_idempotent_second_run_costs_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp, ["Allucinazione"])
            answer = json.dumps([{"id": "allucinazione", "symptoms": "frasi sintomo"}])
            enrich_notes(paths, StaticRouter(FakeLLMProvider([answer])))
            self.assertEqual(enrich_estimate(paths)["notes"], 0)
            llm = FakeLLMProvider([])
            report = enrich_notes(paths, StaticRouter(llm))
            self.assertEqual(llm.prompts, [])
            self.assertEqual(report["enriched"], 0)

    def test_malformed_batch_skipped_not_fatal(self) -> None:
        titles = [f"Nota {i:02d}" for i in range(BATCH_SIZE + 2)]  # 2 lotti
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp, titles)
            good = json.dumps(
                [
                    {"id": f"nota-{i:02d}", "symptoms": "sintomo"}
                    for i in range(BATCH_SIZE, BATCH_SIZE + 2)
                ]
            )
            report = enrich_notes(paths, StaticRouter(FakeLLMProvider(["NON-JSON", good])))
            self.assertEqual(report["failed_batches"], 1)
            self.assertEqual(report["enriched"], 2)

    def test_cli_estimate_then_yes(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            _brain(tmp, ["Allucinazione"])
            llm = FakeLLMProvider([])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["enrich", "--root", tmp], llm=llm)
            self.assertEqual(0, code)
            self.assertEqual(llm.prompts, [])  # estimate = zero calls
            self.assertIn("--yes", out.getvalue())
            answer = json.dumps([{"id": "allucinazione", "symptoms": "si inventa le cose"}])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["enrich", "--yes", "--root", tmp], llm=FakeLLMProvider([answer]))
            self.assertEqual(0, code)
            self.assertIn("enriched 1", out.getvalue())


if __name__ == "__main__":
    unittest.main()
