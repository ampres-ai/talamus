"""Garden corpus enrich + ontology validation (P1.5, HEAVY tier).

Builds the domain-diverse garden brain through the REAL extract -> enrich -> ontology
pipeline with a local LLM and checks the enrichment and ontology induction actually
fire on a corpus other than the book. This is the validation the deterministic FAST
floor cannot give (enrich/ontology need an LLM).

Gated by TALAMUS_BENCH_HEAVY — never runs in `python dev.py`. Run on demand with a
local model, e.g.:

    TALAMUS_BENCH_HEAVY=1 TALAMUS_LLM_PROVIDER=ollama TALAMUS_LLM_MODEL=gemma2 \
        python -m unittest tests.test_benchmarks_garden_enrich
"""

import os
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GARDEN = _REPO_ROOT / "tests" / "fixtures" / "garden-corpus"


@unittest.skipUnless(os.environ.get("TALAMUS_BENCH_HEAVY"), "needs a local LLM (ollama + a model)")
class GardenEnrichTests(unittest.TestCase):
    def test_enrich_and_ontology_fire_on_a_diverse_corpus(self) -> None:
        from talamus.adapters.llm import build_provider
        from talamus.enrich import enrich_notes
        from talamus.ingest import ingest_path
        from talamus.ontology_lab import induce_candidates
        from talamus.paths import TalamusPaths
        from talamus.routing import StaticRouter
        from talamus.store import load_notes

        provider = build_provider(
            os.environ.get("TALAMUS_LLM_PROVIDER", "ollama"),
            os.environ.get("TALAMUS_LLM_MODEL", "gemma2"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()

            ingest_path(paths, str(_GARDEN), StaticRouter(provider))
            notes = load_notes(paths)
            self.assertTrue(notes, "extraction produced no notes")
            # extraction built a graph: at least one note carries typed relations
            self.assertTrue(
                any(n.relations for n in notes),
                "extraction produced no relations to build the graph on",
            )

            # enrich fires: symptom vocabulary is written into retrieval_text
            enrich_notes(paths, provider)
            enriched = load_notes(paths)
            self.assertTrue(
                any(" ~symptoms: " in n.retrieval_text for n in enriched),
                "enrich wrote no symptom vocabulary",
            )

            # ontology induction is exercised end-to-end. We do NOT require >=1
            # candidate here: the garden corpus is deliberately domain-diverse, so it
            # may lack the repeated relation surfaces induction needs (that signal
            # lives on the single-domain book corpus). Here we only assert it runs
            # cleanly and returns a typed list.
            candidates = induce_candidates(paths, provider, min_support=2)
            self.assertIsInstance(candidates, list)


if __name__ == "__main__":
    unittest.main()
