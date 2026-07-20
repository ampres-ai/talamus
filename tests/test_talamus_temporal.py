import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from talamus.errors import TalamusError
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.store import overwrite_note_json, rebuild_indexes, write_note
from talamus.temporal import (
    claims_as_of,
    current_claims,
    invalidate_claim,
    note_timeline,
    parse_when,
    record_claim,
)
from talamus.timeline import note_as_of
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


class ParseWhenTests(unittest.TestCase):
    def test_year_month_date_order(self) -> None:
        self.assertLess(parse_when("2025").instant_utc, parse_when("2026").instant_utc)
        self.assertLess(parse_when("2026-01").instant_utc, parse_when("2026-02").instant_utc)
        self.assertLess(parse_when("2026-01-14").instant_utc, parse_when("2026-01-15").instant_utc)

    def test_partial_dates_mean_end_of_period(self) -> None:
        # "as of January" includes things that happened mid-January
        mid_january = "2026-01-15T12:00:00+00:00"
        self.assertGreater(parse_when("2026-01").instant_utc, mid_january)
        self.assertGreater(parse_when("2026").instant_utc, "2026-06-15T00:00:00+00:00")

    def test_full_datetime_with_timezone_no_warning(self) -> None:
        parsed = parse_when("2026-01-15T12:00:00+01:00")
        self.assertIsNone(parsed.warning)
        self.assertTrue(parsed.instant_utc.startswith("2026-01-15T11:00:00"))

    def test_naive_datetime_warns_and_uses_local_tz(self) -> None:
        parsed = parse_when("2026-01-15T12:00:00")
        self.assertIsNotNone(parsed.warning)
        self.assertIn("local", parsed.warning)

    def test_invalid_raises_actionable_error(self) -> None:
        with self.assertRaises(TalamusError):
            parse_when("ieri pomeriggio")


class ClaimOverlayTests(unittest.TestCase):
    def test_record_invalidate_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            claim = record_claim(paths, "nota-x", "Il cielo è blu", evidence="src#1")
            self.assertEqual(len(current_claims(paths, "nota-x")), 1)
            closed = invalidate_claim(paths, claim.claim_id, invalidated_by="correction")
            self.assertIsNotNone(closed)
            self.assertEqual(current_claims(paths, "nota-x"), [])  # excluded from NOW
            # double-invalidation is a no-op
            self.assertIsNone(invalidate_claim(paths, claim.claim_id, "again"))

    def test_invalidated_claim_still_queryable_as_of_its_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            claim = record_claim(
                paths, "nota-x", "Vecchio fatto", valid_from="2026-01-01T00:00:00+00:00"
            )
            invalidate_claim(
                paths, claim.claim_id, "correction", valid_to="2026-03-01T00:00:00+00:00"
            )
            then = claims_as_of(paths, parse_when("2026-02"), "nota-x")
            self.assertEqual(len(then), 1)
            self.assertEqual(then[0].text, "Vecchio fatto")
            after = claims_as_of(paths, parse_when("2026-04"), "nota-x")
            self.assertEqual(after, [])


class CorrectionIntegrationTests(unittest.TestCase):
    def _brain(self, tmp: str) -> TalamusPaths:
        paths = TalamusPaths(Path(tmp))
        paths.ensure_directories()
        (Path(tmp) / "raw").mkdir(exist_ok=True)
        (Path(tmp) / "raw" / "a.md").write_text("La fonte dice: il valore è 42.", encoding="utf-8")
        write_note(paths, _note("Valore", "Il valore è 41."))
        rebuild_indexes(paths)
        return paths

    def test_correction_closes_old_claim_and_opens_new(self) -> None:
        from talamus.correct import apply_correction

        with tempfile.TemporaryDirectory() as tmp:
            paths = self._brain(tmp)
            llm = FakeLLMProvider(
                [json.dumps({"ok": False, "summary": "Il valore è 42.", "body": "Corretto: 42."})]
            )
            self.assertTrue(apply_correction(paths, "Valore", StaticRouter(llm)))
            now = current_claims(paths, "valore")
            self.assertEqual(len(now), 1)
            self.assertEqual(now[0].text, "Il valore è 42.")  # only the corrected fact is current
            timeline = note_timeline(paths, "Valore")
            invalidated = [c for c in timeline["valid"] if c["invalidated_by"] == "correction"]
            self.assertEqual(len(invalidated), 1)
            self.assertEqual(invalidated[0]["text"], "Il valore è 41.")  # old fact kept, closed


class AsOfReadTests(unittest.TestCase):
    def test_note_as_of_returns_the_old_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            frozen = datetime(2026, 7, 20, 9, 40, tzinfo=UTC)
            with patch("talamus.store._utc_now", return_value=frozen):
                write_note(paths, _note("Concetto", "Prima versione."))
                first = note_as_of(paths, "Concetto", "2999")  # latest
                self.assertEqual(first["summary"], "Prima versione.")
                t1 = first["updated_at"]
                overwrite_note_json(paths, _note("Concetto", "Seconda versione."))
            rebuild_indexes(paths)
            old = note_as_of(paths, "Concetto", t1)
            self.assertEqual(old["summary"], "Prima versione.")
            latest = note_as_of(paths, "Concetto", "2999")
            self.assertEqual(latest["summary"], "Seconda versione.")
            self.assertGreater(latest["updated_at"], t1)

    def test_cli_read_as_of_and_timeline(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Concetto", "Prima versione."))
            t1 = note_as_of(paths, "Concetto", "2999")["updated_at"]
            overwrite_note_json(paths, _note("Concetto", "Seconda versione."))
            rebuild_indexes(paths)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["read", "Concetto", "--as-of", t1, "--root", tmp])
            self.assertEqual(0, code)
            self.assertIn("Prima versione.", out.getvalue())
            self.assertEqual(0, main(["timeline", "Concetto", "--root", tmp]))

    def test_cli_ask_as_of_uses_old_content(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Concetto", "Prima versione."))
            t1 = note_as_of(paths, "Concetto", "2999")["updated_at"]
            overwrite_note_json(paths, _note("Concetto", "Seconda versione."))
            rebuild_indexes(paths)
            llm = FakeLLMProvider(["Risposta storica [1]."])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(
                    ["ask", "concetto prima versione", "--as-of", t1, "--root", tmp], llm=llm
                )
            self.assertEqual(0, code)
            # the answer prompt was built from the OLD version, not the current one
            answer_prompt = llm.prompts[-1]
            self.assertIn("Prima versione.", answer_prompt)
            self.assertNotIn("Seconda versione.", answer_prompt)


if __name__ == "__main__":
    unittest.main()
