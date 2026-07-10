import tempfile
import unittest
from pathlib import Path

from talamus.ask import answer_question
from talamus.domains import load_overview, save_overview
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.store import rebuild_indexes, write_note
from tests.support import FakeLLMProvider


def _note(title: str, retrieval: str) -> CanonicalNote:
    src = SourceRef("raw/a.md", "norm/a#1", "s", "sha256:x", ["c"])
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=[],
        folder="",
        tags=[],
        summary=f"{title}.",
        retrieval_text=retrieval,
        body_sections={"d": retrieval},
        proposed_links=[],
        relations=[],
        sources=[src],
        confidence=0.9,
    )


def _brain(tmp: str) -> TalamusPaths:
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    write_note(paths, _note("Nota Recupero", "recupero indice ricerca"))
    write_note(paths, _note("Nota Tempo", "tempo storia versioni"))
    rebuild_indexes(paths)
    save_overview(
        paths,
        [
            {"name": "Recupero", "description": "Come si cerca.", "members": ["Nota Recupero"]},
            {"name": "Tempo", "description": "Storia e versioni.", "members": ["Nota Tempo"]},
        ],
    )
    return paths


class DomainIdTests(unittest.TestCase):
    def test_save_overview_assigns_stable_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            overview = load_overview(paths)
            ids = [d["id"] for d in overview]
            self.assertEqual(ids, ["dom-recupero", "dom-tempo"])
            # re-saving keeps existing ids
            save_overview(paths, overview)
            self.assertEqual([d["id"] for d in load_overview(paths)], ids)

    def test_duplicate_names_get_distinct_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            save_overview(paths, [{"name": "X", "members": []}, {"name": "X", "members": []}])
            ids = [d["id"] for d in load_overview(paths)]
            self.assertEqual(len(set(ids)), 2)


class StructuredRoutingTests(unittest.TestCase):
    def test_routing_picks_domain_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            trace: dict = {}
            # queue: routing, query expansion, answer
            llm = FakeLLMProvider(["dom-tempo", "tempo versioni", "Risposta sul tempo [1]."])
            answer = answer_question(
                paths, "che versioni esistono?", StaticRouter(llm), trace=trace
            )
            self.assertIn("Risposta sul tempo", answer)
            self.assertEqual(trace["domains_chosen"], ["dom-tempo"])
            self.assertFalse(trace["routing_fallback"])
            self.assertEqual(trace["route"], "overview")
            # the routed note was actually read
            self.assertTrue(any("Nota-Tempo" in p for p in trace["items_read"]))

    def test_routing_falls_back_to_name_matching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            trace: dict = {}
            # queue: routing (name fallback), query expansion, answer
            llm = FakeLLMProvider(["Recupero", "recupero ricerca", "Risposta sul recupero [1]."])
            answer = answer_question(paths, "come cerco?", StaticRouter(llm), trace=trace)
            self.assertIn("Risposta sul recupero", answer)
            self.assertTrue(trace["routing_fallback"])

    def test_trace_reports_index_route_when_overview_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            trace: dict = {}
            # routing returns nothing valid and no name matches -> index path
            llm = FakeLLMProvider(["nessuno", "Risposta [1]."])
            answer_question(paths, "recupero indice ricerca", StaticRouter(llm), trace=trace)
            self.assertEqual(trace["route"], "index")
            self.assertGreater(trace["context_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
