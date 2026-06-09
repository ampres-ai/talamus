import tempfile
import unittest
from pathlib import Path

from talamus.sources import extract_text, is_url


class SourcesTests(unittest.TestCase):
    def test_extract_text_plain_and_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "a.md"
            md.write_text("# Hello\nworld", encoding="utf-8")
            self.assertIn("Hello", extract_text(md))

            html = Path(tmp) / "b.html"
            html.write_text(
                "<html><body><p>Ciao mondo</p><script>secret</script></body></html>",
                encoding="utf-8",
            )
            text = extract_text(html)
            self.assertIn("Ciao mondo", text)
            self.assertNotIn("secret", text)

    def test_is_url(self) -> None:
        self.assertTrue(is_url("https://example.com"))
        self.assertFalse(is_url("notes.md"))


if __name__ == "__main__":
    unittest.main()
