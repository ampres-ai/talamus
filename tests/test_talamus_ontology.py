import unittest

from talamus.models import CanonicalNote, ProposedLink, Relation, SourceRef
from talamus.ontology import build_ontology, neighbors, normalize_relation


def _src() -> SourceRef:
    return SourceRef("raw/a.md", "norm/a#1", "section 1", "sha256:x", ["claim"])


def _note(title, aliases=None, tags=None, relations=None, links=None) -> CanonicalNote:
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=aliases or [],
        folder="",
        tags=tags or [],
        summary=f"{title}.",
        retrieval_text=title,
        body_sections={"summary": f"{title}."},
        proposed_links=links or [],
        relations=relations or [],
        sources=[_src()],
        confidence=0.9,
    )


class OntologyTests(unittest.TestCase):
    def test_normalize_relation_maps_variants(self) -> None:
        self.assertEqual("uses", normalize_relation("usa"))
        self.assertEqual("uses", normalize_relation("uses"))
        self.assertEqual("is-a", normalize_relation("è un tipo di"))
        self.assertEqual("part-of", normalize_relation("parte di"))
        self.assertEqual("contrasts-with", normalize_relation("a differenza di"))
        self.assertEqual("depends-on", normalize_relation("dipende da"))
        self.assertEqual("related", normalize_relation("qualcosa di vago"))

    def test_build_ontology_unifies_target_and_types_edge(self) -> None:
        rag = _note("Retrieval-Augmented Generation", aliases=["RAG"])
        memory = _note("Agent Memory", relations=[Relation("Agent Memory", "usa", "RAG", 0.9)])

        ontology = build_ontology([rag, memory])

        self.assertIn("Agent Memory", ontology["concepts"])
        self.assertEqual(
            [{"source": "Agent Memory", "type": "uses", "target": "Retrieval-Augmented Generation"}],
            ontology["edges"],
        )

    def test_neighbors_both_directions(self) -> None:
        rag = _note("Retrieval-Augmented Generation", aliases=["RAG"])
        memory = _note("Agent Memory", links=[ProposedLink("RAG", "RAG", "uso")])
        ontology = build_ontology([rag, memory])

        self.assertEqual(
            [{"title": "Retrieval-Augmented Generation", "relation": "related", "direction": "out"}],
            neighbors(ontology, "Agent Memory"),
        )
        self.assertEqual(
            [{"title": "Agent Memory", "relation": "related", "direction": "in"}],
            neighbors(ontology, "retrieval-augmented generation"),
        )

    def test_unresolved_target_produces_no_edge(self) -> None:
        memory = _note("Agent Memory", relations=[Relation("Agent Memory", "usa", "Concetto Inesistente", 0.9)])
        self.assertEqual([], build_ontology([memory])["edges"])


if __name__ == "__main__":
    unittest.main()
