"""Read source material of various kinds into plain text for the extractor.

Plain text / Markdown, HTML and Word (.docx) are handled with the standard library.
PDF needs the optional `pdf` extra (`pip install talamus[pdf]`). URLs are fetched and
stripped to text.
"""

from __future__ import annotations

import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from talamus.errors import SourceNotFound, TalamusError

# WordprocessingML namespace for .docx paragraph/run/text elements.
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class _HtmlToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def _strip_html(html: str) -> str:
    parser = _HtmlToText()
    parser.feed(html)
    return "\n".join(parser.parts)


def _pdf_text(path: Path) -> str:
    try:
        import pypdf
    except ImportError as exc:
        raise TalamusError("PDF support needs the 'pdf' extra: pip install talamus[pdf]") from exc
    reader = pypdf.PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _docx_text(path: Path) -> str:
    """Extract paragraph text from a .docx (a zip of XML) with the stdlib only."""
    try:
        with zipfile.ZipFile(path) as archive:
            document = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise TalamusError(f"Not a readable .docx file: {path.name}") from exc
    root = ElementTree.fromstring(document)
    paragraphs: list[str] = []
    for para in root.iter(f"{_W}p"):
        line = "".join(node.text or "" for node in para.iter(f"{_W}t")).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def is_url(target: str) -> bool:
    return target.startswith(("http://", "https://"))


def read_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 (user-provided URL)
        body = response.read().decode("utf-8", errors="replace")
    return _strip_html(body)


def extract_text(path: Path) -> str:
    """Read a source file into plain text, dispatching on its extension."""
    if not path.is_file():
        raise SourceNotFound(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(path)
    if suffix == ".docx":
        return _docx_text(path)
    if suffix in (".html", ".htm"):
        return _strip_html(path.read_text(encoding="utf-8", errors="replace"))
    return path.read_text(encoding="utf-8", errors="replace")
