import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.fde_brain.normalize import normalize_source
from tools.fde_brain.paths import WorkspacePaths


def _fake_pdf_reader(pages_text: list[str], outline: list | None = None):
    class _FakeReader:
        def __init__(self, _path: str) -> None:
            self.pages = [SimpleNamespace(extract_text=lambda t=t: t) for t in pages_text]
            self.outline = outline or []

        def get_destination_page_number(self, item):
            return item.page - 1

    return _FakeReader


class NormalizePackageTests(unittest.TestCase):
    def test_markdown_normalization_writes_manifest_sections_and_quality_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("markdown") / "2026-05-22-my-note.md"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text("# My Note: Pattern\n\nReusable observation.", encoding="utf-8")

            out = normalize_source(
                raw_path=raw,
                category="markdown",
                raw_hash="sha256:abc123",
                captured_at=datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
                paths=paths,
            )

            self.assertTrue(out.ok)
            self.assertEqual("normalized", out.routed_to)
            self.assertIsNotNone(out.manifest_path)
            self.assertIsNotNone(out.quality_report_path)
            self.assertEqual(1, len(out.section_paths))
            self.assertEqual(out.manifest_path, out.output_path)

            manifest = json.loads(out.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("my-note", manifest["source_slug"])
            self.assertEqual("sha256:abc123", manifest["source"]["raw_hash"])
            self.assertEqual("markdown", manifest["source"]["source_type"])
            self.assertEqual(1, len(manifest["sections"]))
            self.assertEqual("001", manifest["sections"][0]["section_id"])
            self.assertEqual("My Note: Pattern", manifest["sections"][0]["title"])

            section = out.section_paths[0].read_text(encoding="utf-8")
            self.assertIn("source-path: AI Space/raw/markdown/2026-05-22-my-note.md", section)
            self.assertIn("section-id: 001", section)
            self.assertIn('section-title: "My Note: Pattern"', section)
            self.assertIn("source-location: markdown", section)
            self.assertIn("classification: reusable-knowledge-candidate", section)
            self.assertIn("# My Note: Pattern", section)

            quality = json.loads(out.quality_report_path.read_text(encoding="utf-8"))
            self.assertEqual(1, quality["section_count"])
            self.assertEqual(0, quality["ocr_pages"])

    @patch(
        "tools.fde_brain.normalize.PdfReader",
        new_callable=lambda: _fake_pdf_reader(
            pages_text=[
                "Book Title\n1\nA hyphen-\nated word. Bad mojibake â€™ quote.",
                "Book Title\n2\nSecond chapter body with enough stable content.",
            ],
            outline=[
                SimpleNamespace(title="Chapter One", page=1),
                SimpleNamespace(title="Chapter Two", page=2),
            ],
        ),
    )
    def test_pdf_package_splits_by_outline_and_cleans_text(self, _reader) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("pdf") / "2026-05-22-book.pdf"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"%PDF-1.4 stub")

            out = normalize_source(
                raw_path=raw,
                category="pdf",
                raw_hash="sha256:pdf",
                captured_at=datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
                paths=paths,
            )

            self.assertTrue(out.ok, msg=str(out))
            self.assertEqual(2, len(out.section_paths))
            first = out.section_paths[0].read_text(encoding="utf-8")
            self.assertIn("source-location: pages 1-1", first)
            self.assertIn("hyphenated word", first)
            self.assertIn("Bad mojibake ' quote.", first)
            self.assertNotIn("\nBook Title\n", first)
            self.assertNotIn("\n1\n", first)

            manifest = json.loads(out.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("pages 1-1", manifest["sections"][0]["locator"])
            self.assertEqual("pages 2-2", manifest["sections"][1]["locator"])
            self.assertTrue(manifest["sections"][0]["next_section"].endswith("002-chapter-two.md"))

    def test_epub_package_preserves_spine_order(self) -> None:
        import zipfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("epub") / "2026-05-22-book.epub"
            raw.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(raw, "w") as zf:
                zf.writestr("META-INF/container.xml", """<?xml version='1.0'?>
<container><rootfiles><rootfile full-path='OPS/package.opf'/></rootfiles></container>""")
                zf.writestr("OPS/package.opf", """<?xml version='1.0'?>
<package xmlns='http://www.idpf.org/2007/opf'>
  <manifest>
    <item id='c1' href='chapter%201.xhtml#body' media-type='application/xhtml+xml'/>
    <item id='c2' href='chapter2.xhtml' media-type='application/xhtml+xml'/>
  </manifest>
  <spine><itemref idref='c1'/><itemref idref='c2'/></spine>
</package>""")
                zf.writestr("OPS/chapter 1.xhtml", "<html><body><h1>First</h1><p>One.</p></body></html>")
                zf.writestr("OPS/chapter2.xhtml", "<html><body><h1>Second</h1><p>Two.</p></body></html>")

            out = normalize_source(
                raw_path=raw,
                category="epub",
                raw_hash="sha256:epub",
                captured_at=datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
                paths=paths,
            )

            self.assertTrue(out.ok, msg=str(out))
            self.assertEqual(2, len(out.section_paths))
            self.assertIn("# First", out.section_paths[0].read_text(encoding="utf-8"))
            self.assertIn("# Second", out.section_paths[1].read_text(encoding="utf-8"))
            manifest = json.loads(out.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("epub spine 1", manifest["sections"][0]["locator"])
            self.assertEqual("epub spine 2", manifest["sections"][1]["locator"])


if __name__ == "__main__":
    unittest.main()
