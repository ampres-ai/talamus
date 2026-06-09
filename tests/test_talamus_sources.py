import tempfile
import unittest
import zipfile
from pathlib import Path

from talamus.errors import TalamusError
from talamus.sources import extract_text, is_url

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    document = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{_W_NS}"><w:body>{body}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


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

    def test_extract_docx_paragraphs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "doc.docx"
            _write_docx(docx, ["Primo paragrafo.", "Secondo paragrafo."])
            text = extract_text(docx)
            self.assertIn("Primo paragrafo.", text)
            self.assertIn("Secondo paragrafo.", text)

    def test_bad_docx_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "broken.docx"
            bad.write_text("this is not a zip", encoding="utf-8")
            with self.assertRaises(TalamusError):
                extract_text(bad)

    def test_is_url(self) -> None:
        self.assertTrue(is_url("https://example.com"))
        self.assertFalse(is_url("notes.md"))


if __name__ == "__main__":
    unittest.main()
