import importlib.util
import unittest

_HAS_FLET = importlib.util.find_spec("flet") is not None


@unittest.skipUnless(_HAS_FLET, "flet not installed (ui extra)")
class WikilinkConversionTests(unittest.TestCase):
    """Pure conversion logic of the Flet UI — no window needed."""

    def _convert(self, text: str) -> str:
        from talamus.ui.app import _wikilinks_to_md

        return _wikilinks_to_md(text)

    def test_plain_wikilink_becomes_angle_bracketed_link(self) -> None:
        self.assertEqual(self._convert("see [[Embedding]]"), "see [Embedding](<Embedding>)")

    def test_aliased_wikilink_uses_label_and_target(self) -> None:
        self.assertEqual(
            self._convert("[[Embedding|gli embedding]]"), "[gli embedding](<Embedding>)"
        )

    def test_target_with_spaces_stays_one_url(self) -> None:
        self.assertEqual(self._convert("[[Vector Store]]"), "[Vector Store](<Vector Store>)")

    def test_text_without_wikilinks_is_unchanged(self) -> None:
        self.assertEqual(self._convert("nessun link qui"), "nessun link qui")


if __name__ == "__main__":
    unittest.main()
