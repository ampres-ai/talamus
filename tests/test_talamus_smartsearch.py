"""Smart search: Query2doc-style LLM query expansion in front of lexical search.

The lexical ceiling (dev/research/2026-06-rs4-search-ceiling.md) is broken by
expanding the query with the user's own LLM before searching — measured on both
corpora (book hit 0.861 → 0.972, docs 0.618 → 0.782). Cached on disk so repeated
queries are free; degrades to plain search on any engine failure."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from talamus.errors import EngineFailed
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.smartsearch import _cache_path, expand_query
from talamus.store import rebuild_indexes, write_note
from tests.support import FakeLLMProvider


def _note(title: str, retrieval_text: str) -> CanonicalNote:
    note = CanonicalNote.minimal(
        title, sources=[SourceRef("raw/a.md", "raw/a.md#1", "s", "sha256:x", ["c"])]
    )
    import dataclasses

    return dataclasses.replace(note, retrieval_text=retrieval_text)


def _brain(tmp: str) -> TalamusPaths:
    paths = TalamusPaths(Path(tmp))
    paths.ensure_directories()
    write_note(paths, _note("Allucinazione", "allucinazione hallucination"))
    write_note(paths, _note("Quantizzazione", "quantizzazione quantization"))
    rebuild_indexes(paths)
    return paths


class SmartSearchTests(unittest.TestCase):
    def test_expansion_is_appended_and_cached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            llm = FakeLLMProvider(["hallucination makes things up"])
            out = expand_query(paths, "il modello inventa", llm)
            self.assertIn("il modello inventa", out)
            self.assertIn("hallucination", out)
            self.assertTrue(_cache_path(paths).is_file())
            # second call hits the cache: no further LLM calls
            again = expand_query(paths, "il modello inventa", FakeLLMProvider([]))
            self.assertEqual(out, again)

    def test_degrades_to_plain_query_on_engine_failure(self) -> None:
        class Down:
            def complete(self, prompt: str) -> str:
                raise EngineFailed("engine down")

        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            out = expand_query(paths, "una domanda", Down())
            self.assertEqual(out, "una domanda")  # never worse than plain search
            self.assertFalse(_cache_path(paths).is_file())  # nothing cached on failure

    def test_empty_query_is_returned_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _brain(tmp)
            self.assertEqual(expand_query(paths, "   ", FakeLLMProvider([])), "   ")

    def test_cli_smart_expands_before_search(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            _brain(tmp)
            # the brain has no lexical match for the vague phrasing; the expansion does
            llm = FakeLLMProvider(["quantization ridurre memoria modello"])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(
                    ["search", "ridurre i bit del modello", "--smart", "--root", tmp], llm=llm
                )
            self.assertEqual(0, code)
            self.assertIn("Quantizzazione", out.getvalue())
            self.assertEqual(len(llm.prompts), 1)  # one expansion call


if __name__ == "__main__":
    unittest.main()
