import tempfile
import unittest
from pathlib import Path

from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import load_notes, rebuild_indexes, reindex, write_note, write_note_json


def _note(title: str) -> CanonicalNote:
    source = SourceRef("raw/a.md", "norm/a#1", "section 1", "sha256:x", [f"{title} claim"])
    return CanonicalNote.minimal(title, sources=[source])


class StoreTests(unittest.TestCase):
    def test_write_note_creates_markdown_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()

            write_note(paths, _note("Retrieval-Augmented Generation"))

            self.assertTrue((paths.notes / "Retrieval-Augmented-Generation.md").is_file())
            self.assertTrue((paths.notes_cache / "retrieval-augmented-generation.json").is_file())

    def test_load_notes_round_trips_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Vector Store"))

            loaded = load_notes(paths)

            self.assertEqual(1, len(loaded))
            self.assertEqual("Vector Store", loaded[0].title)
            self.assertEqual(1, len(loaded[0].sources))

    def test_rebuild_indexes_makes_graph_and_bm25(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Retrieval-Augmented Generation"))

            rebuild_indexes(paths)

            self.assertTrue(paths.graph_file.is_file())
            self.assertTrue(paths.index_file.is_file())

    def test_write_note_json_merges_same_concept_across_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            n1 = CanonicalNote(
                note_id="vector-store",
                title="Vector Store",
                aliases=["VS"],
                folder="",
                tags=["infra"],
                summary="primo",
                retrieval_text="r1",
                body_sections={"d": "x"},
                proposed_links=[],
                relations=[],
                sources=[SourceRef("raw/a.md", "norm/a#1", "la", "sha256:a", ["c1"])],
                confidence=0.8,
            )
            n2 = CanonicalNote(
                note_id="vector-store",
                title="Vector Store",
                aliases=["vettori"],
                folder="",
                tags=["ricerca"],
                summary="secondo",
                retrieval_text="r2",
                body_sections={"d": "y"},
                proposed_links=[],
                relations=[],
                sources=[SourceRef("raw/b.md", "norm/b#1", "lb", "sha256:b", ["c2"])],
                confidence=0.9,
            )

            write_note_json(paths, n1)
            write_note_json(paths, n2)

            notes = load_notes(paths)
            self.assertEqual(1, len(notes))
            merged = notes[0]
            self.assertEqual(2, len(merged.sources))  # provenienza accumulata
            self.assertIn("infra", merged.tags)
            self.assertIn("ricerca", merged.tags)
            self.assertEqual("secondo", merged.summary)  # prose from the higher-confidence one
            self.assertEqual(0.9, merged.confidence)

    def test_rebuild_indexes_persists_ontology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Vector Store"))

            rebuild_indexes(paths)

            from talamus.ontology import load_ontology

            self.assertTrue(paths.ontology_file.is_file())
            self.assertIn("Vector Store", load_ontology(paths)["concepts"])

    def test_reindex_reflects_hand_edits_and_keeps_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            note = CanonicalNote(
                note_id="vector-store",
                title="Vector Store",
                aliases=["VS"],
                folder="",
                tags=["infra"],
                summary="Original summary.",
                retrieval_text="vector store embeddings",
                body_sections={"core_idea": "Stores embeddings."},
                proposed_links=[],
                relations=[],
                sources=[SourceRef("raw/a.md", "norm/a#1", "section 1", "sha256:x", ["claim"])],
                confidence=0.9,
            )
            write_note(paths, note)
            md = paths.notes / "Vector-Store.md"
            md.write_text(
                md.read_text(encoding="utf-8").replace("Original summary.", "Edited by hand."),
                encoding="utf-8",
            )

            reindex(paths)

            loaded = {n.note_id: n for n in load_notes(paths)}
            self.assertIn("vector-store", loaded)
            self.assertEqual("Edited by hand.", loaded["vector-store"].summary)
            self.assertEqual(1, len(loaded["vector-store"].sources))


if __name__ == "__main__":
    unittest.main()
