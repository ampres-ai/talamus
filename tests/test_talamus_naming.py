import unittest

from talamus.naming import note_filename, note_slug


class NamingTests(unittest.TestCase):
    def test_spaces_become_dashes(self) -> None:
        self.assertEqual("Vector-Store", note_slug("Vector Store"))

    def test_strips_characters_invalid_on_windows(self) -> None:
        slug = note_slug("I/O: Notes? *Draft* <v2>")
        for bad in '<>:"/\\|?*':
            self.assertNotIn(bad, slug)

    def test_filename_has_md_extension(self) -> None:
        self.assertEqual("Vector-Store.md", note_filename("Vector Store"))

    def test_empty_or_only_invalid_falls_back(self) -> None:
        self.assertEqual("untitled", note_slug("///"))


if __name__ == "__main__":
    unittest.main()
