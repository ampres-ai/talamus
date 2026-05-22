import unittest
from pathlib import Path

from tools.fde_brain.classify import classify


class ClassifyTests(unittest.TestCase):
    def test_markdown_extensions(self) -> None:
        self.assertEqual("markdown", classify(Path("note.md")))
        self.assertEqual("markdown", classify(Path("note.markdown")))

    def test_text_extension(self) -> None:
        self.assertEqual("text", classify(Path("doc.txt")))

    def test_pdf_extension(self) -> None:
        self.assertEqual("pdf", classify(Path("paper.pdf")))

    def test_image_extensions(self) -> None:
        self.assertEqual("image", classify(Path("screenshot.png")))
        self.assertEqual("image", classify(Path("photo.jpg")))
        self.assertEqual("image", classify(Path("photo.jpeg")))
        self.assertEqual("image", classify(Path("anim.gif")))
        self.assertEqual("image", classify(Path("scan.tiff")))
        self.assertEqual("image", classify(Path("art.webp")))
        self.assertEqual("image", classify(Path("bitmap.bmp")))

    def test_unknown_extension(self) -> None:
        self.assertEqual("unknown", classify(Path("random.xyz")))
        self.assertEqual("unknown", classify(Path("noextension")))

    def test_case_insensitive(self) -> None:
        self.assertEqual("pdf", classify(Path("DOC.PDF")))
        self.assertEqual("image", classify(Path("Photo.JPG")))
        self.assertEqual("markdown", classify(Path("Note.MD")))


if __name__ == "__main__":
    unittest.main()
