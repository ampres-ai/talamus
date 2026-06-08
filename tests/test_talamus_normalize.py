import unittest

from talamus.normalize import normalize_text


class NormalizeTests(unittest.TestCase):
    def test_splits_by_top_level_headings_and_records_provenance(self) -> None:
        text = "# Intro\nRAG collega il modello a fonti esterne.\n\n# Uso\nQuando i dati cambiano spesso."

        package = normalize_text("knowledge/raw/note.md", text)

        self.assertEqual("knowledge/raw/note.md", package.raw_path)
        self.assertTrue(package.source_hash.startswith("sha256:"))
        self.assertEqual(2, len(package.sections))
        self.assertEqual("Intro", package.sections[0].title)
        self.assertIn("RAG", package.sections[0].text)

    def test_text_without_headings_becomes_single_section(self) -> None:
        package = normalize_text("a.txt", "Solo un paragrafo.")

        self.assertEqual(1, len(package.sections))
        self.assertEqual("a.txt", package.sections[0].title)


if __name__ == "__main__":
    unittest.main()
