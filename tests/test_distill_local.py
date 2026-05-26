import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fde_brain.distill_local import distill_normalized_sections
from tools.fde_brain.paths import WorkspacePaths


def _ollama_response(payload: dict) -> dict:
    return {"message": {"content": json.dumps(payload)}}


class DistillLocalTests(unittest.TestCase):
    @patch("tools.fde_brain.distill_local.ollama.chat")
    def test_gemma_json_candidates_render_obsidian_notes_with_provenance(self, chat_mock) -> None:
        chat_mock.return_value = _ollama_response(
            {
                "notes": [
                    {
                        "title": "Reusable Pattern",
                        "type": "pattern",
                        "aliases": ["Reusable Pattern", "Pattern: Reuse"],
                        "summary": "A stable reusable implementation idea.",
                        "core_idea": "Extract repeatable decisions into a named pattern.",
                        "practical_use": "Use it when similar client problems recur.",
                        "related": ["AI Engineering"],
                        "tags": ["ai-engineering", "patterns"],
                        "confidence": 0.91,
                        "supported_claims": ["Patterns reduce repeated design work."],
                    }
                ]
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            section = paths.normalized_for("markdown") / "source" / "sections" / "001-source.md"
            section.parent.mkdir(parents=True, exist_ok=True)
            section.write_text(
                "---\n"
                "source-path: AI Space/raw/markdown/source.md\n"
                "source-hash: sha256:abc\n"
                "source-location: markdown\n"
                "section-id: 001\n"
                "---\n\n"
                "# Source\n\nReusable content.",
                encoding="utf-8",
            )

            result = distill_normalized_sections(
                section_paths=[section],
                paths=paths,
                run_id="run-1",
                model="gemma4:e4b",
                existing_targets={"AI-Engineering"},
            )

        self.assertTrue(result.ok, msg=result.error)
        self.assertEqual(1, len(result.notes))
        note = result.notes[0]
        self.assertEqual("Reusable Pattern", note.title)
        self.assertIn("aliases:", note.content)
        self.assertIn("raw_path: AI Space/raw/markdown/source.md", note.content)
        self.assertIn("normalized_path: AI Space/normalized/markdown/source/sections/001-source.md", note.content)
        self.assertIn("source_hash: sha256:abc", note.content)
        self.assertIn("## Practical Use", note.content)
        self.assertIn("[[AI-Engineering|AI Engineering]]", note.content)
        self.assertIn("  - \"Pattern: Reuse\"", note.content)

    @patch("tools.fde_brain.distill_local.ollama.chat")
    def test_malformed_json_routes_chunk_to_review_without_promoting(self, chat_mock) -> None:
        chat_mock.return_value = {"message": {"content": "not json"}}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            section = paths.normalized_for("text") / "source" / "sections" / "001-source.md"
            section.parent.mkdir(parents=True, exist_ok=True)
            section.write_text(
                "---\nsource-path: AI Space/raw/text/source.txt\nsource-hash: sha256:x\n"
                "source-location: text\n---\n\n# Source\n\nText.",
                encoding="utf-8",
            )

            result = distill_normalized_sections([section], paths, run_id="bad-json")

        self.assertTrue(result.ok)
        self.assertEqual([], result.notes)
        self.assertEqual(1, len(result.review_items))
        self.assertIn("json", result.review_items[0]["error"].lower())

    @patch("tools.fde_brain.distill_local.ollama.chat")
    def test_crlf_frontmatter_preserves_source_provenance(self, chat_mock) -> None:
        chat_mock.return_value = _ollama_response(
            {
                "notes": [
                    {
                        "title": "CRLF Concept",
                        "type": "concept",
                        "aliases": ["CRLF Concept"],
                        "summary": "Summary.",
                        "core_idea": "Core.",
                        "practical_use": "Use.",
                        "related": [],
                        "tags": ["ai-engineering"],
                        "confidence": 0.9,
                        "supported_claims": ["Claim."],
                    }
                ]
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = WorkspacePaths(root)
            paths.ensure_directories()
            section = paths.normalized_for("text") / "source" / "sections" / "001-source.md"
            section.parent.mkdir(parents=True, exist_ok=True)
            section.write_text(
                "---\r\nsource-path: AI Space/raw/text/source.txt\r\nsource-hash: sha256:x\r\n"
                "source-location: text\r\n---\r\n\r\n# Source\r\n\r\nText.",
                encoding="utf-8",
            )

            result = distill_normalized_sections([section], paths, run_id="crlf")

        self.assertTrue(result.ok)
        self.assertEqual(1, len(result.notes))
        self.assertIn("raw_path: AI Space/raw/text/source.txt", result.notes[0].content)


if __name__ == "__main__":
    unittest.main()
