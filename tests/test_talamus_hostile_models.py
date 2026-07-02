"""'Hostile model' battery: the product must stay excellent even with weak
engines (product rule, 2026-06-12 — the focus is ANY user, not the test brain).
Cheap models answer with truncated, malformed, empty, prose-wrapped JSON and
literal control characters: every point of the engine that consumes LLM output
must degrade gracefully, never corrupt."""

import tempfile
import unittest
from pathlib import Path

from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.store import rebuild_indexes, write_note
from tests.support import FakeLLMProvider

HOSTILE = [
    "",  # empty
    "Sure! Here are the results you asked for.",  # prose without JSON
    '[{"title": "Rotto",',  # truncated
    '{"oggetto": "non array"}',  # wrong type
    '```json\n[{"id": 1}]\n```extra',  # fence + garbage
]


def _note(title: str) -> CanonicalNote:
    return CanonicalNote.minimal(
        title, sources=[SourceRef("raw/a.md", "raw/a.md#1", "s", "sha256:x", ["c"])]
    )


def _brain(tmp: str, titles: list[str]) -> TalamusPaths:
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    for title in titles:
        write_note(paths, _note(title))
    rebuild_indexes(paths)
    return paths


class HostileExtractionTests(unittest.TestCase):
    def test_extract_raises_actionable_error_not_garbage(self) -> None:
        from talamus.extract import extract_notes
        from talamus.normalize import normalize_text

        package = normalize_text("raw/a.md", "Testo sorgente.")
        for raw in HOSTILE:
            try:
                notes = extract_notes(package, StaticRouter(FakeLLMProvider([raw])))
            except ValueError:
                continue  # clean, actionable error: acceptable
            self.assertEqual(notes, [])  # otherwise empty list: NEVER corrupt notes

    def test_control_characters_in_strings_are_tolerated(self) -> None:
        from talamus.extract import _extract_json_array

        raw = '[{"title": "Nota\ncon a capo", "summary": "ok"}]'
        parsed = _extract_json_array(raw)
        self.assertEqual(len(parsed), 1)


class HostileRoutingTests(unittest.TestCase):
    def test_garbage_routing_falls_back_to_index_path(self) -> None:
        from talamus.ask import answer_question
        from talamus.domains import save_overview

        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp, ["Concetto"])
            save_overview(paths, [{"name": "Dominio", "description": "d", "members": ["Concetto"]}])
            for raw in HOSTILE:
                trace: dict = {}
                llm = FakeLLMProvider([raw, raw, raw, "Risposta [1]."])
                answer = answer_question(paths, "concetto", StaticRouter(llm), trace=trace)
                self.assertNotIn("Traceback", answer)
                self.assertTrue(trace["items_read"])  # something is ALWAYS read


class HostileDomainsTests(unittest.TestCase):
    def test_batched_induction_survives_garbage(self) -> None:
        from talamus.domains import _name_domains_batched

        clusters = [[f"N{i}" for i in range(30)], ["A", "B", "C"], ["Sola"]]
        summaries = {t: "s" for c in clusters for t in c}
        for raw in HOSTILE:
            domains = _name_domains_batched(
                clusters, summaries, StaticRouter(FakeLLMProvider([raw] * 5))
            )
            members = sorted(m for d in domains for m in d["members"])
            self.assertEqual(members, sorted(summaries))  # every note stays mapped


class HostileEnrichTests(unittest.TestCase):
    def test_enrich_never_pollutes_retrieval_text(self) -> None:
        from talamus.enrich import enrich_notes
        from talamus.store import load_notes

        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp, ["Concetto"])
            original = load_notes(paths)[0].retrieval_text
            junk = (
                '[{"id": "concetto", "symptoms": "' + "x" * 800 + '"}]',  # beyond the cap
                '[{"id": "concetto", "symptoms": "{\\"json\\": \\"dentro\\"}"}]',  # structure
                *HOSTILE,
            )
            for raw in junk:
                report = enrich_notes(paths, StaticRouter(FakeLLMProvider([raw])))
                self.assertEqual(report["enriched"], 0)
            self.assertEqual(load_notes(paths)[0].retrieval_text, original)


class HostileConsolidateTests(unittest.TestCase):
    def test_detection_returns_empty_not_wrong(self) -> None:
        from talamus.consolidate import find_duplicates

        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp, ["Alfa", "Beta"])
            for raw in HOSTILE:
                self.assertEqual(find_duplicates(paths, StaticRouter(FakeLLMProvider([raw]))), [])


class HostileTieredProviderTests(unittest.TestCase):
    """P2: the new model/effort constructor args must not change how hostile engine
    output is handled — a tiered provider degrades exactly like an untiered one."""

    def test_tiered_providers_still_degrade_gracefully(self) -> None:
        from talamus.adapters.llm import build_provider_for_task
        from talamus.config import TalamusConfig
        from talamus.extract import extract_notes
        from talamus.normalize import normalize_text

        package = normalize_text("raw/a.md", "Testo sorgente.")
        for provider_name in ("claude-cli", "codex-cli", "gemini-cli"):
            for tier, effort in (("economy", "low"), ("quality", "high")):
                for raw in HOSTILE:
                    provider = build_provider_for_task(
                        provider_name, TalamusConfig.default(), tier, effort
                    )
                    provider._runner = lambda args, prompt, raw=raw: raw  # type: ignore[attr-defined]
                    try:
                        notes = extract_notes(package, StaticRouter(provider))
                    except ValueError:
                        continue  # clean, actionable error: acceptable
                    self.assertEqual(notes, [])  # never corrupt notes


if __name__ == "__main__":
    unittest.main()
