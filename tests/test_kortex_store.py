import tempfile
import unittest
from pathlib import Path

from kortex.models import CanonicalNote, SourceRef
from kortex.paths import KortexPaths
from kortex.store import load_notes, rebuild_indexes, reindex, write_note


def _note(title: str) -> CanonicalNote:
    source = SourceRef("raw/a.md", "norm/a#1", "section 1", "sha256:x", [f"{title} claim"])
    return CanonicalNote.minimal(title, sources=[source])


class StoreTests(unittest.TestCase):
    def test_write_note_creates_markdown_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = KortexPaths(Path(tmp))
            paths.ensure_directories()

            write_note(paths, _note("Retrieval-Augmented Generation"))

            self.assertTrue((paths.notes / "Retrieval-Augmented-Generation.md").is_file())
            self.assertTrue((paths.notes_cache / "retrieval-augmented-generation.json").is_file())

    def test_load_notes_round_trips_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = KortexPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Vector Store"))

            loaded = load_notes(paths)

            self.assertEqual(1, len(loaded))
            self.assertEqual("Vector Store", loaded[0].title)
            self.assertEqual(1, len(loaded[0].sources))

    def test_rebuild_indexes_makes_graph_and_bm25(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = KortexPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Retrieval-Augmented Generation"))

            rebuild_indexes(paths)

            self.assertTrue(paths.graph_file.is_file())
            self.assertTrue(paths.index_file.is_file())


    def test_reindex_reflects_hand_edits_and_keeps_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = KortexPaths(Path(tmp))
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
