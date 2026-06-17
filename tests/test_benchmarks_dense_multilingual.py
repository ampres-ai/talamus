import unittest

from benchmarks.shootout.systems.dense_multilingual import (
    MultilingualDenseSystem,
    e5_passage_text,
    e5_query_text,
)


class E5PrefixTests(unittest.TestCase):
    def test_query_prefix(self):
        self.assertEqual(e5_query_text("quantizzazione"), "query: quantizzazione")

    def test_passage_prefix(self):
        self.assertEqual(e5_passage_text("Titolo", "corpo"), "passage: Titolo corpo")

    def test_passage_prefix_strips_empty_title(self):
        self.assertEqual(e5_passage_text("", "corpo"), "passage:  corpo".strip())

    def test_system_name_and_default_model(self):
        sys = MultilingualDenseSystem()
        self.assertEqual(sys.name, "dense-multilingual")


if __name__ == "__main__":
    unittest.main()
