import dataclasses
import tempfile
import unittest
from pathlib import Path

from talamus.models import CanonicalNote, Relation, SourceRef
from talamus.paths import TalamusPaths
from talamus.relations import list_relations, prune_relations
from talamus.store import load_notes, write_note


def _note(title: str, relations: list[Relation]) -> CanonicalNote:
    base = CanonicalNote.minimal(title, sources=[SourceRef("r", "n", "l", "sha256:x", ["c"])])
    return dataclasses.replace(base, relations=relations)


class RelationsTests(unittest.TestCase):
    def test_list_and_prune_by_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(
                paths,
                _note(
                    "A",
                    [
                        Relation("A", "uses", "B", 0.9),
                        Relation("A", "related", "C", 0.2),
                    ],
                ),
            )

            self.assertEqual(2, len(list_relations(paths)))

            pruned = prune_relations(paths, 0.5)

            self.assertEqual(1, pruned)
            note = next(n for n in load_notes(paths) if n.title == "A")
            self.assertEqual(1, len(note.relations))
            self.assertEqual("B", note.relations[0].target)


if __name__ == "__main__":
    unittest.main()
