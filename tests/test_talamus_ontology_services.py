import json
import tempfile
import unittest
from pathlib import Path

from talamus.models import CanonicalNote, Relation, SourceRef
from talamus.ontology_lab import induce_candidates, surface_key
from talamus.paths import TalamusPaths
from talamus.services.ontology import (
    apply_ontology_candidate,
    deprecate_ontology_type,
    export_ontology_schema,
    get_ontology_history,
    get_ontology_status,
    list_ontology_candidates,
    reject_ontology_candidate,
)
from talamus.store import rebuild_indexes, write_note
from tests.support import FakeLLMProvider


def _note(title: str, retrieval: str, relations: list[tuple[str, str]]) -> CanonicalNote:
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
        relations=[Relation(title, rel, target, 0.9) for rel, target in relations],
        sources=[src],
        confidence=0.9,
    )


def _brain(tmp: str) -> TalamusPaths:
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    write_note(paths, _note("Compilatore", "compilatore note schede", [("alimenta", "Hub Sync")]))
    write_note(paths, _note("Estrattore", "estrattore llm concetti", [("alimenta", "Compilatore")]))
    write_note(paths, _note("Scanner", "scanner repository codice", [("alimenta", "Compilatore")]))
    write_note(paths, _note("Hub Sync", "hub sync puntatori brain", []))
    rebuild_indexes(paths)
    return paths


def _naming_response(key: str) -> str:
    return json.dumps(
        [
            {
                "cluster_key": key,
                "name": "alimenta",
                "definition": "Il soggetto fornisce dati o contenuto al bersaglio.",
                "inverse": "alimentato-da",
            }
        ]
    )


def _induce(paths: TalamusPaths) -> str:
    key = surface_key("alimenta")
    created = induce_candidates(paths, FakeLLMProvider([_naming_response(key)]))
    return created[0].id


class TalamusOntologyServiceTests(unittest.TestCase):
    def test_status_and_candidates_are_typed_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            type_id = _induce(paths)

            status = get_ontology_status(tmp)
            candidates = list_ontology_candidates(tmp)

        self.assertTrue(status.success, status.message)
        self.assertIsNotNone(status.data)
        assert status.data is not None
        self.assertGreaterEqual(status.data.version, 1)
        self.assertIn("candidate", status.data.types)
        self.assertTrue(candidates.success, candidates.message)
        self.assertIsNotNone(candidates.data)
        assert candidates.data is not None
        self.assertEqual(type_id, candidates.data[0].id)
        self.assertEqual("candidate", candidates.data[0].status)

    def test_apply_reject_deprecate_history_and_export_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            type_id = _induce(paths)

            applied = apply_ontology_candidate(tmp, type_id, force=True)
            deprecated = deprecate_ontology_type(tmp, type_id, reason="superseded")
            history = get_ontology_history(tmp)
            exported = export_ontology_schema(tmp)

        self.assertTrue(applied.success, applied.message)
        self.assertTrue(deprecated.success, deprecated.message)
        self.assertTrue(history.success, history.message)
        self.assertIsNotNone(history.data)
        assert history.data is not None
        events = [event.get("event") for event in history.data.events]
        self.assertIn("promoted", events)
        self.assertIn("deprecated", events)
        self.assertTrue(exported.success, exported.message)
        self.assertIsNotNone(exported.data)
        assert exported.data is not None
        self.assertEqual(type_id, exported.data.schema["relation_types"][0]["id"])

    def test_reject_candidate_returns_decision_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            type_id = _induce(paths)

            rejected = reject_ontology_candidate(tmp, type_id, reason="not enough value")
            candidates = list_ontology_candidates(tmp)

        self.assertTrue(rejected.success, rejected.message)
        self.assertIsNotNone(rejected.data)
        assert rejected.data is not None
        self.assertEqual(type_id, rejected.data.type_id)
        self.assertEqual("rejected", rejected.data.action)
        self.assertTrue(candidates.success, candidates.message)
        self.assertEqual([], candidates.data)


if __name__ == "__main__":
    unittest.main()
