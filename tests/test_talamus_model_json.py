import unittest

from talamus.model_json import balanced_objects, json_array, json_object


class ModelJsonTests(unittest.TestCase):
    def test_json_array_extracts_wrapped_array_with_control_chars(self) -> None:
        raw = 'before\n[{"title": "line\\nbreak"}]\nafter'

        parsed = json_array(raw)

        self.assertEqual(parsed, [{"title": "line\nbreak"}])

    def test_json_object_extracts_wrapped_object_with_control_chars(self) -> None:
        raw = 'answer: {"ok": false, "body": "line\\nbreak"}'

        parsed = json_object(raw)

        self.assertEqual(parsed, {"ok": False, "body": "line\nbreak"})

    def test_balanced_objects_salvages_complete_objects_from_truncated_json(self) -> None:
        raw = '[{"canonical": "A", "members": ["A", "B"]}, {"canonical": "C"'

        parsed = balanced_objects(raw)

        self.assertEqual(parsed, [{"canonical": "A", "members": ["A", "B"]}])


if __name__ == "__main__":
    unittest.main()
