import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from talamus.correct import (
    apply_proposed_correction,
    provenance_status,
    verify_batch,
)
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.review import ReviewQueue
from talamus.routing import StaticRouter
from talamus.store import load_notes, rebuild_indexes, write_note
from talamus.timeline import note_history
from tests.support import FakeLLMProvider


def _note(
    title: str,
    summary: str,
    source_rel: str,
    confidence: float = 0.9,
    source_hash: str = "sha256:x",
) -> CanonicalNote:
    src = SourceRef(source_rel, f"{source_rel}#1", "s", source_hash, ["c"])
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
        confidence=confidence,
    )


def _brain(tmp: str) -> TalamusPaths:
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    (Path(tmp) / "raw").mkdir(exist_ok=True)
    (Path(tmp) / "raw" / "buona.md").write_text("La fonte: il valore è 42.", encoding="utf-8")
    write_note(paths, _note("Fedele", "Il valore è 42.", "raw/buona.md"))
    write_note(paths, _note("Sbagliata", "Il valore è 41.", "raw/buona.md"))
    write_note(paths, _note("Orfana", "Senza fonte sul disco.", "raw/sparita.md"))
    write_note(paths, _note("Incerta", "Poco sicura.", "raw/buona.md", confidence=0.3))
    rebuild_indexes(paths)
    return paths


class ProvenanceTests(unittest.TestCase):
    def test_status_detects_missing_and_low_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            by_title = {n.title: n for n in load_notes(paths)}
            self.assertEqual(provenance_status(paths, by_title["Fedele"])["status"], "ok")
            self.assertEqual(
                provenance_status(paths, by_title["Orfana"])["status"], "source_missing"
            )
            self.assertEqual(
                provenance_status(paths, by_title["Incerta"])["status"], "low_confidence"
            )

    def test_real_hash_matches_despite_windows_newlines(self) -> None:
        """Book-run regression: source_hash is computed on the extracted TEXT;
        the check must re-extract from the RAW file, not hash file bytes —
        otherwise CRLF on disk (or resolving the derived normalized view)
        marks every healthy note as changed (243/243 stale on the real book)."""
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            text = "Il valore è 42.\nSeconda riga.\n"
            raw = Path(tmp) / "raw"
            raw.mkdir(exist_ok=True)
            (raw / "vera.md").write_text(text, encoding="utf-8")  # CRLF su Windows
            real_hash = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
            write_note(paths, _note("Vera", "Il valore è 42.", "raw/vera.md", 0.9, real_hash))
            rebuild_indexes(paths)
            by_title = {n.title: n for n in load_notes(paths)}
            self.assertEqual(provenance_status(paths, by_title["Vera"])["status"], "ok")
            # and when the source REALLY changes, it says so
            (raw / "vera.md").write_text("Contenuto riscritto.", encoding="utf-8")
            self.assertEqual(provenance_status(paths, by_title["Vera"])["status"], "source_changed")


class VerifyBatchTests(unittest.TestCase):
    def test_batch_is_deterministic_and_routes_to_review(self) -> None:
        """M7 gate: stale -> review item without crash and without LLM; wrong note ->
        correction PROPOSED (not auto-applied); faithful note -> ok."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            ok = json.dumps({"ok": True})
            wrong = json.dumps({"ok": False, "summary": "Il valore è 42.", "body": "Corretto."})
            llm = FakeLLMProvider([ok, wrong])  # Fedele, then Sbagliata (sorted note order)
            report = verify_batch(paths, StaticRouter(llm))
            self.assertEqual(report["stale"], 2)  # Orfana (missing) + Incerta (low confidence)
            self.assertEqual(report["checked"], 2)
            self.assertEqual(report["ok"], 1)
            self.assertEqual(report["corrections_proposed"], 1)
            queue = ReviewQueue(paths)
            kinds = {i.kind for i in queue.list(status="pending")}
            self.assertEqual(kinds, {"stale_source", "correction"})
            # the wrong note was NOT silently overwritten (F7.4)
            by_title = {n.title: n for n in load_notes(paths)}
            self.assertEqual(by_title["Sbagliata"].summary, "Il valore è 41.")

    def test_only_stale_makes_no_llm_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            llm = FakeLLMProvider([])
            report = verify_batch(paths, StaticRouter(llm), only_stale=True)
            self.assertEqual(llm.prompts, [])
            self.assertEqual(report["stale"], 2)
            self.assertEqual(report["checked"], 0)

    def test_source_filter_limits_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            llm = FakeLLMProvider([json.dumps({"ok": True})] * 3)
            report = verify_batch(paths, StaticRouter(llm), source_filter="sparita")
            self.assertEqual(report["skipped"], 3)
            self.assertEqual(report["stale"], 1)  # only Orfana selected, and it's stale


class ReviewApplyCorrectionTests(unittest.TestCase):
    def test_applying_a_proposed_correction_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            detail = {"title": "Sbagliata", "summary": "Il valore è 42.", "body": "Corretto."}
            self.assertTrue(apply_proposed_correction(paths, detail))
            by_title = {n.title: n for n in load_notes(paths)}
            self.assertEqual(by_title["Sbagliata"].summary, "Il valore è 42.")
            versions = note_history(paths, "Sbagliata")
            self.assertGreaterEqual(len(versions), 2)  # the old version is preserved
            self.assertEqual(versions[0]["summary"], "Il valore è 41.")

    def test_cli_review_apply_correction_end_to_end(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            queue = ReviewQueue(paths)
            item = queue.add(
                "correction",
                "Sbagliata: non combacia",
                {"title": "Sbagliata", "summary": "Il valore è 42.", "body": "Corretto."},
            )
            self.assertEqual(0, main(["review", "apply", item.item_id, "--root", tmp]))
            by_title = {n.title: n for n in load_notes(paths)}
            self.assertEqual(by_title["Sbagliata"].summary, "Il valore è 42.")
            self.assertEqual(queue.get(item.item_id).status, "applied")


class CliVerifyBatchTests(unittest.TestCase):
    def test_cli_verify_stale(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            _brain(tmp)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["verify", "--stale", "--root", tmp], llm=FakeLLMProvider([]))
            self.assertEqual(0, code)
            self.assertIn("stale sources", out.getvalue())

    def test_cli_verify_without_args_is_actionable(self) -> None:
        from contextlib import redirect_stderr

        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            _brain(tmp)
            err = io.StringIO()
            with redirect_stderr(err):
                code = main(["verify", "--root", tmp], llm=FakeLLMProvider([]))
            self.assertEqual(1, code)
            self.assertIn("--all", err.getvalue())


if __name__ == "__main__":
    unittest.main()
