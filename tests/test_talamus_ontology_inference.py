import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from talamus.cli import main
from talamus.models import CanonicalNote, Relation, SourceRef
from talamus.ontology import load_inferred_ontology
from talamus.ontology_lab import (
    RelationType,
    Schema,
    infer_property_candidates,
    load_schema,
    promote_candidate,
    read_history,
    save_schema,
    surface_key,
)
from talamus.paths import TalamusPaths
from talamus.recall import concept_neighbors
from talamus.services.graph import list_graph_neighbors
from talamus.store import rebuild_indexes, write_note


def _src() -> SourceRef:
    return SourceRef("raw/a.md", "norm/a#1", "s", "sha256:x", ["c"])


def _note(title: str, relations: list[tuple[str, str]] | None = None) -> CanonicalNote:
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=[],
        folder="",
        tags=[],
        summary=f"{title}.",
        retrieval_text=title,
        body_sections={"summary": f"{title}."},
        proposed_links=[],
        relations=[Relation(title, relation, target, 0.9) for relation, target in relations or []],
        sources=[_src()],
        confidence=0.9,
    )


def _active_type(name: str, **properties: object) -> RelationType:
    return RelationType(
        id=f"rel:{name}",
        name=name,
        definition=f"{name} relation.",
        surfaces=[surface_key(name)],
        support=8,
        distinct_notes=3,
        confidence=0.9,
        status="active",
        valid_from="2026-07-08T00:00:00+00:00",
        **properties,
    )


def _seed_schema(paths: TalamusPaths, *types: RelationType) -> None:
    save_schema(
        paths,
        Schema(
            version=1,
            schema_id="schema-test",
            created_at="2026-07-08T00:00:00+00:00",
            relation_types=list(types),
        ),
    )


def _write_notes(paths: TalamusPaths, notes: list[CanonicalNote]) -> None:
    paths.ensure_directories()
    for note in notes:
        write_note(paths, note)
    rebuild_indexes(paths)


def _inverse_notes(with_witnesses: bool) -> list[CanonicalNote]:
    notes: list[CanonicalNote] = []
    for index in range(8):
        reporter = f"Reporter {index}"
        finding = f"Finding {index}"
        notes.append(_note(reporter, [("reports", finding)]))
        reverse = [("is-reported-by", reporter)] if with_witnesses else []
        notes.append(_note(finding, reverse))
    return notes


def _transitive_notes(with_witnesses: bool) -> list[CanonicalNote]:
    notes: list[CanonicalNote] = []
    for index in range(8):
        parent = f"Parent {index}"
        child = f"Child {index}"
        grandchild = f"Grandchild {index}"
        parent_edges = [("contains", child)]
        if with_witnesses:
            parent_edges.append(("contains", grandchild))
        notes.append(_note(parent, parent_edges))
        notes.append(_note(child, [("contains", grandchild)]))
        notes.append(_note(grandchild))
    return notes


def _writable_temp_root() -> Path:
    if os.environ.get("TALAMUS_TEST_TMPDIR"):
        return Path(os.environ["TALAMUS_TEST_TMPDIR"])
    windows_tmp = Path("C:/tmp")
    if os.name == "nt" and windows_tmp.is_dir():
        return windows_tmp
    return Path(tempfile.gettempdir())


class _IsolatedHomeTest(unittest.TestCase):
    def setUp(self) -> None:
        from unittest.mock import patch

        old_tempdir = tempfile.tempdir
        tempfile.tempdir = str(_writable_temp_root())
        self.addCleanup(lambda: setattr(tempfile, "tempdir", old_tempdir))
        self._home = tempfile.TemporaryDirectory()
        patcher = patch.dict(os.environ, {"TALAMUS_HOME": self._home.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._home.cleanup)


class PropertyInductionTests(_IsolatedHomeTest):
    def test_inverse_candidate_requires_reverse_witness_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("reports"), _active_type("is-reported-by"))
            _write_notes(paths, _inverse_notes(with_witnesses=False))

            self.assertEqual([], infer_property_candidates(paths))

            _write_notes(paths, _inverse_notes(with_witnesses=True))
            candidates = infer_property_candidates(paths)

        inverse = [c for c in candidates if c.property == "inverse_of"]
        self.assertEqual(1, len(inverse))
        candidate = inverse[0]
        self.assertEqual("property", candidate.kind)
        self.assertEqual("rel:reports", candidate.type_id)
        self.assertEqual("rel:is-reported-by", candidate.value)
        self.assertEqual(8, candidate.support)
        self.assertGreaterEqual(candidate.distinct_notes, 3)
        self.assertTrue(candidate.witnesses)

    def test_transitive_candidate_requires_explicit_corpus_witnesses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("contains"))
            _write_notes(paths, _transitive_notes(with_witnesses=False))

            self.assertEqual([], infer_property_candidates(paths))

            _write_notes(paths, _transitive_notes(with_witnesses=True))
            candidates = infer_property_candidates(paths)

        transitive = [c for c in candidates if c.property == "transitive"]
        self.assertEqual(1, len(transitive))
        self.assertEqual("rel:contains", transitive[0].type_id)
        self.assertEqual(8, transitive[0].support)

    def test_symmetric_candidate_uses_bidirectional_unordered_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("collaborates-with"))
            notes: list[CanonicalNote] = []
            for index in range(8):
                left = f"Left {index}"
                right = f"Right {index}"
                notes.append(_note(left, [("collaborates-with", right)]))
                notes.append(_note(right, [("collaborates-with", left)]))
            _write_notes(paths, notes)

            candidates = infer_property_candidates(paths)

        symmetric = [c for c in candidates if c.property == "symmetric"]
        self.assertEqual(1, len(symmetric))
        self.assertEqual("rel:collaborates-with", symmetric[0].type_id)


class PropertyInductionIdempotenceTests(_IsolatedHomeTest):
    def test_infer_does_not_repropose_known_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("contains"))
            _write_notes(paths, _transitive_notes(with_witnesses=True))

            first = infer_property_candidates(paths)
            second = infer_property_candidates(paths)

        self.assertTrue(first)
        self.assertEqual([], second)


class PropertyPromotionTests(_IsolatedHomeTest):
    def test_property_promotion_updates_schema_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("contains"))
            _write_notes(paths, _transitive_notes(with_witnesses=True))
            candidate = next(
                c for c in infer_property_candidates(paths) if c.property == "transitive"
            )

            ok, message = promote_candidate(paths, candidate.id)

            self.assertTrue(ok, message)
            schema = load_schema(paths)
            rel_type = schema.by_id("rel:contains")
            self.assertIsNotNone(rel_type)
            assert rel_type is not None
            self.assertTrue(rel_type.transitive)
            events = [event["event"] for event in read_history(paths)]
            self.assertIn("property_candidate_induced", events)
            self.assertIn("property_promoted", events)

    def test_inverse_promotion_links_both_types_and_closure_fills_missing_reverse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("reports"), _active_type("is-reported-by"))
            notes = _inverse_notes(with_witnesses=True)
            notes.append(_note("Reporter X", [("reports", "Finding X")]))
            notes.append(_note("Finding X"))
            _write_notes(paths, notes)
            candidate = next(
                c for c in infer_property_candidates(paths) if c.property == "inverse_of"
            )

            ok, message = promote_candidate(paths, candidate.id)

            self.assertTrue(ok, message)
            schema = load_schema(paths)
            reports = schema.by_id("rel:reports")
            reported = schema.by_id("rel:is-reported-by")
            assert reports is not None and reported is not None
            self.assertEqual("rel:is-reported-by", reports.inverse_of)
            self.assertEqual("rel:reports", reported.inverse_of)
            inferred = load_inferred_ontology(paths)["edges"]

        keys = {(e["source"], e["relation"], e["target"]) for e in inferred}
        self.assertIn(("Finding X", "is-reported-by", "Reporter X"), keys)
        # witnessed pairs already have explicit reverse edges: never re-derived
        self.assertNotIn(("Finding 0", "is-reported-by", "Reporter 0"), keys)
        rules = {e["rule"] for e in inferred}
        self.assertEqual({"inverse_of"}, rules)


class ClosureTests(_IsolatedHomeTest):
    def test_closure_is_deterministic_cycle_safe_and_depth_capped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("contains", transitive=True))
            _write_notes(
                paths,
                [
                    _note("A", [("contains", "B")]),
                    _note("B", [("contains", "C")]),
                    _note("C", [("contains", "D")]),
                    _note("D", [("contains", "A")]),
                ],
            )

            first = json.dumps(load_inferred_ontology(paths), sort_keys=True)
            rebuild_indexes(paths)
            second_data = load_inferred_ontology(paths)
            second = json.dumps(second_data, sort_keys=True)

        self.assertEqual(first, second)
        inferred = {(e["source"], e["relation"], e["target"]) for e in second_data["edges"]}
        self.assertIn(("A", "contains", "C"), inferred)
        self.assertIn(("B", "contains", "D"), inferred)
        self.assertNotIn(("A", "contains", "D"), inferred)
        self.assertTrue(all(edge["source"] != edge["target"] for edge in second_data["edges"]))

    def test_inferred_edges_carry_provenance_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("contains", transitive=True))
            _write_notes(
                paths,
                [
                    _note("A", [("contains", "B")]),
                    _note("B", [("contains", "C")]),
                    _note("C"),
                ],
            )

            inferred = load_inferred_ontology(paths)["edges"]

        self.assertEqual(1, len(inferred))
        edge = inferred[0]
        self.assertEqual("transitive", edge["rule"])
        self.assertTrue(edge["inferred"])
        self.assertEqual(2, len(edge["via"]))
        self.assertEqual(1, edge["schema_version"])

    def test_symmetric_closure_derives_the_missing_direction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("collaborates-with", symmetric=True))
            _write_notes(
                paths,
                [
                    _note("A", [("collaborates-with", "B")]),
                    _note("B"),
                ],
            )

            inferred = load_inferred_ontology(paths)["edges"]

        self.assertEqual(1, len(inferred))
        edge = inferred[0]
        self.assertEqual(
            ("B", "collaborates-with", "A"), (edge["source"], edge["relation"], edge["target"])
        )
        self.assertEqual("symmetric", edge["rule"])
        self.assertEqual(1, len(edge["via"]))


class NeighborInferenceTests(_IsolatedHomeTest):
    def test_neighbors_include_marked_inferred_edges_and_opt_out_hides_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("contains", transitive=True))
            _write_notes(
                paths,
                [
                    _note("A", [("contains", "B")]),
                    _note("B", [("contains", "C")]),
                    _note("C"),
                ],
            )

            core_with = concept_neighbors(paths, "A")
            core_without = concept_neighbors(paths, "A", include_inferred=False)
            service_with = list_graph_neighbors(tmp, "A")
            service_without = list_graph_neighbors(tmp, "A", include_inferred=False)
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["neighbors", "A", "--root", tmp]))
            out_no = io.StringIO()
            with redirect_stdout(out_no):
                self.assertEqual(0, main(["neighbors", "A", "--root", tmp, "--no-inferred"]))

        self.assertTrue(any(item["title"] == "C" and item.get("inferred") for item in core_with))
        self.assertFalse(any(item["title"] == "C" for item in core_without))
        self.assertIsNotNone(service_with.data)
        assert service_with.data is not None
        self.assertTrue(any(item.title == "C" and item.inferred for item in service_with.data))
        self.assertIsNotNone(service_without.data)
        assert service_without.data is not None
        self.assertFalse(any(item.title == "C" for item in service_without.data))
        self.assertIn("-> [contains] C (inferred: transitive via", out.getvalue())
        self.assertNotIn("C (inferred:", out_no.getvalue())


class CliInferTests(_IsolatedHomeTest):
    def test_cli_infer_review_apply_flow_for_properties(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("contains"))
            _write_notes(paths, _transitive_notes(with_witnesses=True))

            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["ontology", "infer", "--root", tmp]))
            self.assertIn("prop:transitive:rel:contains", out.getvalue())

            review_out = io.StringIO()
            with redirect_stdout(review_out):
                self.assertEqual(0, main(["ontology", "review", "--root", tmp]))
            self.assertIn("[property] transitive", review_out.getvalue())

            apply_out = io.StringIO()
            with redirect_stdout(apply_out):
                self.assertEqual(
                    0, main(["ontology", "apply", "prop:transitive:rel:contains", "--root", tmp])
                )
            rel_type = load_schema(paths).by_id("rel:contains")
            assert rel_type is not None
            self.assertTrue(rel_type.transitive)


try:
    import mcp  # noqa: F401

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@unittest.skipUnless(HAS_MCP, "mcp not installed (optional extra talamus[mcp])")
class McpNeighborInferenceTests(_IsolatedHomeTest):
    def test_mcp_neighbors_support_inferred_opt_out_parameter(self) -> None:
        from talamus import mcp_server

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            _seed_schema(paths, _active_type("contains", transitive=True))
            _write_notes(
                paths,
                [
                    _note("A", [("contains", "B")]),
                    _note("B", [("contains", "C")]),
                    _note("C"),
                ],
            )
            mcp_server._root = Path(tmp)
            try:
                with_inferred = mcp_server.neighbors("A")
                without_inferred = mcp_server.neighbors("A", include_inferred=False)
            finally:
                mcp_server._root = Path(".").resolve()

        self.assertIn("C (inferred: transitive via", with_inferred)
        self.assertNotIn("C", without_inferred)


if __name__ == "__main__":
    unittest.main()
