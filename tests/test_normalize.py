import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.fde_brain.ocr import OcrResult
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


class NormalizeMarkdownTests(unittest.TestCase):
    def test_passthrough_writes_frontmatter_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("markdown") / "2026-05-22-note.md"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text("# Title\nbody text", encoding="utf-8")

            out = normalize_source(
                raw_path=raw,
                category="markdown",
                raw_hash="sha256:abc123",
                captured_at=datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
                paths=paths,
            )

            self.assertTrue(out.ok)
            self.assertEqual("normalized", out.routed_to)
            assert out.output_path is not None
            self.assertTrue(out.output_path.exists())
            self.assertTrue(str(out.package_dir).startswith(str(paths.normalized_for("markdown"))))
            self.assertEqual(1, len(out.section_paths))
            content = out.section_paths[0].read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"))
            self.assertIn("source-type: markdown", content)
            self.assertIn("source-hash: sha256:abc123", content)
            self.assertIn("parser: passthrough", content)
            self.assertIn("# Title", content)


class NormalizeTextTests(unittest.TestCase):
    def test_text_writes_to_text_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("text") / "2026-05-22-doc.txt"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text("Plain text here.\nSecond line.", encoding="utf-8")

            out = normalize_source(
                raw_path=raw,
                category="text",
                raw_hash="sha256:def",
                captured_at=datetime.now(timezone.utc),
                paths=paths,
            )

            self.assertTrue(out.ok)
            assert out.output_path is not None
            self.assertEqual(paths.normalized_for("text") / "doc", out.package_dir)
            self.assertEqual(1, len(out.section_paths))
            self.assertIn("Plain text here.", out.section_paths[0].read_text(encoding="utf-8"))


class NormalizePdfTests(unittest.TestCase):
    @patch("tools.fde_brain.normalize.PdfReader", new_callable=lambda: _fake_pdf_reader(
        [
            "This is the first page with enough text to clear the digital threshold for normalization.",
            "Second page content with additional words for completeness and segmentation testing.",
        ]
    ))
    def test_pdf_with_text_segments_by_page(self, _reader) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("pdf") / "2026-05-22-paper.pdf"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"%PDF-1.4 stub")

            out = normalize_source(
                raw_path=raw,
                category="pdf",
                raw_hash="sha256:pdf",
                captured_at=datetime.now(timezone.utc),
                paths=paths,
            )

            self.assertTrue(out.ok, msg=str(out))
            self.assertEqual("normalized", out.routed_to)
            assert out.output_path is not None
            content = "\n".join(path.read_text(encoding="utf-8") for path in out.section_paths)
            self.assertIn("# Page 1", content)
            self.assertIn("# Page 2", content)
            self.assertIn("parser: pypdf", content)

    @patch(
        "tools.fde_brain.normalize.PdfReader",
        new_callable=lambda: _fake_pdf_reader(
            pages_text=[
                "Intro page text content here",
                "Foo chapter text content here that is long enough",
                "Foo continued more text here for the chapter range",
                "Bar chapter text content here for the second chapter",
                "Bar continued more text content for chapter two",
            ],
            outline=[
                SimpleNamespace(title="Introduction", page=1),
                SimpleNamespace(title="Chapter 1: Foo", page=2),
                SimpleNamespace(title="Chapter 2: Bar", page=4),
            ],
        ),
    )
    def test_pdf_with_outline_uses_chapter_headings(self, _reader) -> None:
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
                raw_hash="sha256:book",
                captured_at=datetime.now(timezone.utc),
                paths=paths,
            )

            self.assertTrue(out.ok)
            assert out.output_path is not None
            content = "\n".join(path.read_text(encoding="utf-8") for path in out.section_paths)
            self.assertIn("# Introduction", content)
            self.assertIn("# Chapter 1: Foo", content)
            self.assertIn("# Chapter 2: Bar", content)
            self.assertNotIn("# Page 1", content)
            self.assertIn("source-location: pages 1-1", content)
            self.assertIn("source-location: pages 2-3", content)
            self.assertIn("source-location: pages 4-5", content)

    def test_layout_aware_ocr_fallback_invokes_ocr_on_visual_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("pdf") / "2026-05-22-mixed.pdf"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"%PDF-1.4 stub")

            fake_reader_cls = _fake_pdf_reader(
                pages_text=[
                    "Text only page one with enough content to exceed the digital threshold for normalization.",
                    "Mixed page with visual content but also some text in it. Adding length to keep things going.",
                    "Final text only page wrapping up the document with a few more characters of body text.",
                ],
            )

            def layout_side_effect(page):
                return getattr(page, "_visual", False)

            fake_reader = fake_reader_cls("ignored")
            fake_reader.pages[1]._visual = True

            ocr_calls: list[Path] = []

            def render_side_effect(raw, idx):
                ocr_calls.append((raw, idx))
                return tmp_png_for(idx)

            def tmp_png_for(idx):
                p = Path(tmp) / f"render-{idx}.png"
                p.write_bytes(b"fake-png")
                return p

            ocr_side_effect = OcrResult(ok=True, text="Visual OCR text for page two", model="glm-ocr")

            with patch("tools.fde_brain.normalize.PdfReader", return_value=fake_reader), \
                 patch("tools.fde_brain.normalize.page_has_visual_content", side_effect=layout_side_effect), \
                 patch("tools.fde_brain.normalize.render_page_to_tempfile", side_effect=render_side_effect), \
                 patch("tools.fde_brain.normalize.extract_text_from_image", return_value=ocr_side_effect) as ocr_mock:
                out = normalize_source(
                    raw_path=raw,
                    category="pdf",
                    raw_hash="sha256:mixed",
                    captured_at=datetime.now(timezone.utc),
                    paths=paths,
                )

            self.assertTrue(out.ok, msg=str(out))
            self.assertEqual("normalized", out.routed_to)
            self.assertEqual(1, ocr_mock.call_count)
            assert out.output_path is not None
            content = "\n".join(path.read_text(encoding="utf-8") for path in out.section_paths)
            self.assertIn("Visual OCR text for page two", content)
            self.assertIn("Text only page one", content)
            self.assertIn("Final text only page", content)

    def test_pdf_without_visual_content_skips_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("pdf") / "2026-05-22-text.pdf"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"%PDF-1.4 stub")

            fake_reader_cls = _fake_pdf_reader(
                pages_text=["Plain text page that has plenty of characters for the threshold and contains zero visual."],
            )

            with patch("tools.fde_brain.normalize.PdfReader", new=fake_reader_cls), \
                 patch("tools.fde_brain.normalize.page_has_visual_content", return_value=False), \
                 patch("tools.fde_brain.normalize.extract_text_from_image") as ocr_mock:
                out = normalize_source(
                    raw_path=raw,
                    category="pdf",
                    raw_hash="sha256:text",
                    captured_at=datetime.now(timezone.utc),
                    paths=paths,
                )

            self.assertTrue(out.ok)
            ocr_mock.assert_not_called()

    @patch("tools.fde_brain.normalize.PdfReader", new_callable=lambda: _fake_pdf_reader(["", ""]))
    def test_pdf_with_no_text_routes_to_review(self, _reader) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("pdf") / "2026-05-22-blank.pdf"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"%PDF-1.4 stub")

            out = normalize_source(
                raw_path=raw,
                category="pdf",
                raw_hash="sha256:blank",
                captured_at=datetime.now(timezone.utc),
                paths=paths,
            )

            self.assertEqual("review", out.routed_to)
            assert out.output_path is not None
            self.assertIn("low-confidence-normalization", out.output_path.as_posix())


class NormalizeImageTests(unittest.TestCase):
    @patch("tools.fde_brain.normalize.extract_text_from_image")
    def test_image_ocr_success(self, ocr_fn) -> None:
        ocr_fn.return_value = OcrResult(ok=True, text="OCR'd content here", model="glm-ocr")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("image") / "2026-05-22-shot.png"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"fake-png")

            out = normalize_source(
                raw_path=raw,
                category="image",
                raw_hash="sha256:img",
                captured_at=datetime.now(timezone.utc),
                paths=paths,
            )

            self.assertTrue(out.ok)
            self.assertEqual("normalized", out.routed_to)
            assert out.output_path is not None
            content = out.section_paths[0].read_text(encoding="utf-8")
            self.assertIn("## OCR", content)
            self.assertIn("OCR'd content here", content)
            self.assertIn("parser: glm-ocr", content)

    @patch("tools.fde_brain.normalize.extract_text_from_image")
    def test_image_ocr_failure(self, ocr_fn) -> None:
        ocr_fn.return_value = OcrResult(ok=False, text="", model="glm-ocr", error="timeout")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw_for("image") / "2026-05-22-fail.png"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"fake-png")

            out = normalize_source(
                raw_path=raw,
                category="image",
                raw_hash="sha256:img2",
                captured_at=datetime.now(timezone.utc),
                paths=paths,
            )

            self.assertFalse(out.ok)
            self.assertEqual("failed", out.routed_to)
            assert out.output_path is not None
            self.assertIn("technical-failures", out.output_path.as_posix())


class NormalizeUnknownTests(unittest.TestCase):
    def test_unknown_routes_to_needs_human(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            raw = paths.raw / "2026-05-22-weird.xyz"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"binary blob")

            out = normalize_source(
                raw_path=raw,
                category="unknown",
                raw_hash="sha256:weird",
                captured_at=datetime.now(timezone.utc),
                paths=paths,
            )

            self.assertEqual("review", out.routed_to)
            assert out.output_path is not None
            self.assertIn("needs-human", out.output_path.as_posix())


if __name__ == "__main__":
    unittest.main()
