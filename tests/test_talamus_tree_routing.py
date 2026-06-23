import json
import tempfile
import unittest
from pathlib import Path

from talamus.ask import answer_question
from talamus.bench import routing_prompt_tokens, routing_prompt_tokens_tree
from talamus.domains import (
    TREE_THRESHOLD,
    build_overview_tree,
    load_overview_tree,
    save_overview,
)
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
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


def _big_brain(tmp: str) -> TalamusPaths:
    """A brain with enough domains to need the tree (TREE_THRESHOLD)."""
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    domains = []
    for index in range(TREE_THRESHOLD):
        title = f"Nota {index:02d}"
        write_note(paths, _note(title, f"argomento{index:02d} contenuto"))
        domains.append(
            {
                "name": f"Dominio {index:02d}",
                "description": f"Tema numero {index}.",
                "members": [title],
            }
        )
    rebuild_indexes(paths)
    save_overview(paths, domains)
    return paths


class TreeBuildTests(unittest.TestCase):
    def test_small_overview_needs_no_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            save_overview(paths, [{"name": "Solo", "members": []}])
            areas = build_overview_tree(paths, FakeLLMProvider([]))
            self.assertEqual(areas, [])
            self.assertEqual(load_overview_tree(paths), [])

    def test_tree_groups_domains_and_catches_leftovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _big_brain(tmp)
            response = json.dumps(
                [
                    {
                        "name": "Prima metà",
                        "description": "I primi temi.",
                        "children": [f"dom-dominio-{i:02d}" for i in range(6)],
                    }
                ]
            )
            areas = build_overview_tree(paths, FakeLLMProvider([response]))
            self.assertEqual(len(areas), 2)  # the named area + "Other" for leftovers
            self.assertEqual(len(areas[0]["children"]), 6)
            self.assertEqual(areas[1]["name"], "Other")
            self.assertEqual(len(areas[1]["children"]), TREE_THRESHOLD - 6)
            self.assertTrue(all(a["id"].startswith("area-") for a in areas))


class TwoLevelRoutingTests(unittest.TestCase):
    def test_ask_routes_area_then_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _big_brain(tmp)
            grouping = json.dumps(
                [
                    {
                        "name": "Area A",
                        "description": "x",
                        "children": [f"dom-dominio-{i:02d}" for i in range(6)],
                    },
                    {
                        "name": "Area B",
                        "description": "y",
                        "children": [f"dom-dominio-{i:02d}" for i in range(6, TREE_THRESHOLD)],
                    },
                ]
            )
            build_overview_tree(paths, FakeLLMProvider([grouping]))
            trace: dict = {}
            # queue: area routing, domain routing, query expansion (RS3), answer
            llm = FakeLLMProvider(["area-area-b", "dom-dominio-07", "prova", "Risposta [1]."])
            answer = answer_question(paths, "domanda di prova", llm, trace=trace)
            self.assertIn("Risposta", answer)
            self.assertEqual(trace["routing_levels"], 2)
            self.assertEqual(trace["areas_chosen"], ["area-area-b"])
            self.assertEqual(trace["domains_chosen"], ["dom-dominio-07"])
            # the second routing prompt listed ONLY area B's domains
            second_prompt = llm.prompts[1]
            self.assertIn("dom-dominio-07", second_prompt)
            self.assertNotIn("dom-dominio-03", second_prompt)
            # the routed note was read
            self.assertTrue(any("Nota-07" in p for p in trace["items_read"]))


class TokenCurveTests(unittest.TestCase):
    def test_tree_routing_is_an_order_of_magnitude_cheaper(self) -> None:
        """Two levels cut routing cost ~10x per level (measured: 12x @10k, ~14x
        @100k); deeper levels are the natural extension toward log(N)."""
        flat_10k = routing_prompt_tokens(10_000)["prompt_tokens"]
        tree_10k = routing_prompt_tokens_tree(10_000)["prompt_tokens"]
        self.assertLess(tree_10k, flat_10k / 10)
        flat_100k = routing_prompt_tokens(100_000)["prompt_tokens"]
        tree_100k = routing_prompt_tokens_tree(100_000)["prompt_tokens"]
        self.assertLess(tree_100k, flat_100k / 10)
        # cross-scale: routing a 100k-note brain with the tree costs LESS than
        # routing a 10k-note brain flat
        self.assertLess(tree_100k, flat_10k)


if __name__ == "__main__":
    unittest.main()
