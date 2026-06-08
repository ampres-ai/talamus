import json
import unittest

from talamus.session import compress_transcript, normalize_session, session_worth_remembering


class SessionTests(unittest.TestCase):
    def test_compress_jsonl_keeps_text_and_compacts_tools(self) -> None:
        jsonl = "\n".join(
            [
                json.dumps({"role": "user", "content": "Correggi il bug in auth.py"}),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Guardo il file."},
                            {"type": "tool_use", "name": "Read", "input": {"file_path": "auth.py"}},
                        ],
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Edit", "input": {"file_path": "auth.py"}},
                            {"type": "text", "text": "Corretto."},
                        ],
                    }
                ),
            ]
        )

        out = compress_transcript(jsonl)

        self.assertIn("Correggi il bug", out)
        self.assertIn("[tool Read: auth.py]", out)
        self.assertIn("[tool Edit: auth.py]", out)
        self.assertIn("Corretto.", out)

    def test_plain_text_is_passthrough(self) -> None:
        self.assertEqual("Solo testo.", compress_transcript("Solo testo."))

    def test_normalize_session_adds_changes_section_when_diff(self) -> None:
        package = normalize_session(
            "raw/s.jsonl", '{"role":"user","content":"ciao"}', "diff --git a/x b/x\n+riga"
        )

        titles = [section.title for section in package.sections]
        self.assertIn("Conversazione", titles)
        self.assertIn("Modifiche", titles)
        self.assertTrue(package.source_hash.startswith("sha256:"))

    def test_normalize_session_without_diff_has_one_section(self) -> None:
        package = normalize_session("raw/s.jsonl", "user: ciao", "")
        self.assertEqual(1, len(package.sections))

    def test_gate_true_with_diff(self) -> None:
        self.assertTrue(session_worth_remembering("ok", "diff --git a/x b/x\n+riga"))

    def test_gate_true_with_long_transcript(self) -> None:
        self.assertTrue(session_worth_remembering("x" * 500, ""))

    def test_gate_false_for_trivial_chat(self) -> None:
        self.assertFalse(session_worth_remembering("ok lancia i test", ""))


if __name__ == "__main__":
    unittest.main()
