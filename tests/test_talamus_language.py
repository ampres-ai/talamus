"""The three-layer language architecture:

1. prompts/instructions: ALWAYS English (cheap local models obey English best);
2. note prose: the user's language (config `language`, locale fallback);
3. machine layer: English canonical (relation verbs, canonical alias, half of
   retrieval_text) — so search and the emergent ontology work across languages.
"""

import json
import tempfile
import unittest
from pathlib import Path

from talamus.config import TalamusConfig, load_config, resolve_language, save_config
from talamus.extract import extract_notes
from talamus.normalize import normalize_text
from talamus.routing import StaticRouter
from tests.support import FakeLLMProvider


class ConfigLanguageTests(unittest.TestCase):
    def test_old_configs_without_language_still_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "talamus.json"
            data = TalamusConfig.default().__dict__.copy()
            data.pop("language")  # a pre-language config file
            path.write_text(json.dumps(data), encoding="utf-8")
            config = load_config(path)
            self.assertEqual(config.language, "")

    def test_explicit_language_wins(self) -> None:
        config = TalamusConfig.default()
        config = type(config)(**{**config.__dict__, "language": "Italian"})
        self.assertEqual(resolve_language(config), "Italian")

    def test_fallback_is_never_empty(self) -> None:
        self.assertTrue(resolve_language(TalamusConfig.default()).strip())

    def test_language_roundtrips_through_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "talamus.json"
            config = TalamusConfig.default()
            config = type(config)(**{**config.__dict__, "language": "German"})
            save_config(path, config)
            self.assertEqual(load_config(path).language, "German")


class ExtractionPromptTests(unittest.TestCase):
    def _prompt_for(self, language: str) -> str:
        llm = FakeLLMProvider(["[]"])
        package = normalize_text("raw/a.md", "Some source text about retrieval.")
        extract_notes(package, StaticRouter(llm), language=language)
        return llm.prompts[0]

    def test_instructions_are_english_with_output_language(self) -> None:
        prompt = self._prompt_for("Italian")
        self.assertIn("expert librarian", prompt)  # English instructions
        self.assertIn("in Italian", prompt)  # output-language directive resolved

    def test_machine_layer_directives_present(self) -> None:
        prompt = self._prompt_for("Italian")
        self.assertIn("canonical name of the concept", prompt)  # canonical alias
        self.assertIn("AND in English", prompt)  # bilingual retrieval_text
        self.assertIn("ENGLISH verbs", prompt)  # canonical relation surfaces

    def test_symptom_vocabulary_directive_present(self) -> None:
        """The semantic bridge for vague questions is paid at ingest —
        retrieval_text must carry the symptom phrasings a user would use to
        describe the problem without knowing its name."""
        prompt = self._prompt_for("Italian")
        self.assertIn("SYMPTOM PHRASINGS", prompt)
        self.assertIn("WITHOUT knowing its name", prompt)

    def test_structural_section_keys_are_fixed(self) -> None:
        prompt = self._prompt_for("German")
        for key in ("definizione", "funzionamento", "relazioni"):
            self.assertIn(key, prompt)  # keys are identifiers, not display text


class AnswerLanguageTests(unittest.TestCase):
    def test_answer_prompt_mirrors_question_language(self) -> None:
        from talamus.ask import _ANSWER_PROMPT

        self.assertIn("SAME LANGUAGE AS THE QUESTION", _ANSWER_PROMPT)

    def test_expansion_is_bilingual(self) -> None:
        from talamus.ask import _EXPAND_PROMPT

        self.assertIn("AND in English", _EXPAND_PROMPT)


if __name__ == "__main__":
    unittest.main()
