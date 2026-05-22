import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fde_brain.distill_long import (
    LongDistillResult,
    PromotedNote,
    distill_long_source,
)
from tools.fde_brain.paths import WorkspacePaths


NORMALIZED_BODY = """---
source-path: AI Space/raw/pdf/2026-05-22-ddia.pdf
source-type: pdf
source-hash: sha256:abc
captured-at: 2026-05-22T12:00:00+00:00
parser: pypdf
parser-confidence: 1.0
---

# ddia

## Chapter 1: Foundations

_Pages 1–10_

Foundation chapter body text.

## Chapter 2: Replication

_Pages 11–25_

Replication chapter body text.
"""


def _proc(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["claude", "-p"], returncode=returncode, stdout=stdout, stderr=stderr)


def _chapter_response(title: str, anchor: str) -> str:
    return json.dumps(
        {
            "notes": [
                {"title": f"{title} Key Idea", "type": "chapter", "body": f"# {title}\n\nMain ideas.", "tags": ["x"], "anchor_used": anchor},
                {"title": f"{title} Concept A", "type": "concept", "body": "Body A", "tags": [], "anchor_used": anchor},
            ]
        }
    )


def _cross_response() -> str:
    return json.dumps(
        {
            "notes": [
                {"title": "Quorum Replication Pattern", "type": "pattern", "body": "Pattern body", "tags": ["pattern"]},
                {"title": "Eventual Consistency", "type": "glossary", "body": "Definition", "tags": ["term"]},
            ]
        }
    )


def _overview_response() -> str:
    return json.dumps(
        {
            "notes": [
                {
                    "title": "DDIA Overview",
                    "type": "overview",
                    "body": "See [[Foundations Key Idea]] and [[Replication Key Idea]].",
                    "tags": ["overview"],
                }
            ]
        }
    )


class DistillLongTests(unittest.TestCase):
    def _write_normalized(self, root: Path) -> tuple[Path, Path, WorkspacePaths]:
        paths = WorkspacePaths(root)
        paths.ensure_directories()
        raw = paths.raw_for("pdf") / "2026-05-22-ddia.pdf"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b"%PDF-1.4 stub")
        normalized = paths.normalized_for("pdf") / "ddia.md"
        normalized.parent.mkdir(parents=True, exist_ok=True)
        normalized.write_text(NORMALIZED_BODY, encoding="utf-8")
        return raw, normalized, paths

    @patch("tools.fde_brain.distill_long.subprocess.run")
    def test_produces_chapter_cross_and_overview_notes(self, run_mock) -> None:
        run_mock.side_effect = [
            _proc(_chapter_response("Foundations", "chapter-1-foundations")),
            _proc(_chapter_response("Replication", "chapter-2-replication")),
            _proc(_cross_response()),
            _proc(_overview_response()),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, normalized, paths = self._write_normalized(root)

            result = distill_long_source(
                normalized_path=normalized, raw_path=raw, paths=paths, run_id="run-42"
            )

            self.assertTrue(result.ok, msg=result.error)
            # 2 chapters * 2 notes + 2 cross + 1 overview = 7
            self.assertEqual(7, len(result.notes))
            types = sorted({n.type for n in result.notes})
            self.assertEqual(["chapter", "concept", "glossary", "overview", "pattern"], types)

            # Every note has a non-empty rendered markdown body with frontmatter
            for note in result.notes:
                self.assertTrue(note.content.startswith("---\n"), msg=note.title)
                self.assertIn(f"type: {note.type}", note.content)
                self.assertIn("ingestion-run: run-42", note.content)
                self.assertIn(f"# {note.title}", note.content)

            # Chapter/concept notes carry source anchors to the normalized chapter heading
            ch_note = next(n for n in result.notes if n.title == "Foundations Key Idea")
            self.assertIn("ddia.md#chapter-1-foundations", "\n".join(ch_note.source_anchors))

            # Cross-source notes cite the whole normalized file
            pattern = next(n for n in result.notes if n.type == "pattern")
            self.assertIn("ddia.md", "\n".join(pattern.source_anchors))

    @patch("tools.fde_brain.distill_long.subprocess.run")
    def test_handles_markdown_fenced_json_response(self, run_mock) -> None:
        fenced = "```json\n" + json.dumps({"notes": [
            {"title": "Foo", "type": "concept", "body": "B", "tags": [], "anchor_used": "chapter-1-foundations"},
        ]}) + "\n```"
        run_mock.side_effect = [
            _proc(fenced),
            _proc(fenced),
            _proc(json.dumps({"notes": []})),
            _proc(json.dumps({"notes": []})),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, normalized, paths = self._write_normalized(root)

            result = distill_long_source(normalized, raw, paths, run_id="x")

            self.assertTrue(result.ok, msg=result.error)
            self.assertGreater(len(result.notes), 0)
            titles = [n.title for n in result.notes]
            self.assertIn("Foo", titles)

    @patch("tools.fde_brain.distill_long.subprocess.run")
    def test_malformed_json_returns_error(self, run_mock) -> None:
        run_mock.return_value = _proc("not json at all")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, normalized, paths = self._write_normalized(root)

            result = distill_long_source(normalized, raw, paths, run_id="x")

            self.assertFalse(result.ok)
            self.assertIn("json", (result.error or "").lower())

    @patch("tools.fde_brain.distill_long.subprocess.run")
    def test_empty_chapter_notes_allowed(self, run_mock) -> None:
        empty = json.dumps({"notes": []})
        run_mock.side_effect = [_proc(empty), _proc(empty), _proc(empty), _proc(empty)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, normalized, paths = self._write_normalized(root)

            result = distill_long_source(normalized, raw, paths, run_id="x")

            self.assertTrue(result.ok)
            self.assertEqual([], result.notes)

    @patch("tools.fde_brain.distill_long.subprocess.run")
    def test_timeout_returns_error(self, run_mock) -> None:
        run_mock.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=5)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, normalized, paths = self._write_normalized(root)

            result = distill_long_source(normalized, raw, paths, run_id="x", timeout_sec=5)

            self.assertFalse(result.ok)
            self.assertIn("timeout", (result.error or "").lower())

    @patch("tools.fde_brain.distill_long.subprocess.run")
    def test_duplicate_titles_get_source_slug_suffix(self, run_mock) -> None:
        dup_chapter = json.dumps(
            {
                "notes": [
                    {"title": "Replication", "type": "chapter", "body": "B", "tags": [], "anchor_used": "chapter-1-foundations"},
                    {"title": "Replication", "type": "concept", "body": "B", "tags": [], "anchor_used": "chapter-1-foundations"},
                ]
            }
        )
        run_mock.side_effect = [
            _proc(dup_chapter),
            _proc(json.dumps({"notes": []})),
            _proc(json.dumps({"notes": []})),
            _proc(json.dumps({"notes": []})),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, normalized, paths = self._write_normalized(root)

            result = distill_long_source(normalized, raw, paths, run_id="x")

            self.assertTrue(result.ok)
            titles = [n.title for n in result.notes]
            self.assertEqual(2, len(titles))
            # First occurrence keeps the bare title; second is suffixed
            self.assertIn("Replication", titles)
            suffixed = [t for t in titles if t != "Replication"]
            self.assertEqual(1, len(suffixed))
            self.assertIn("(ddia)", suffixed[0])

    def test_promoted_note_is_frozen(self) -> None:
        n = PromotedNote(title="x", type="concept", content="---\n---\n", source_anchors=[])
        with self.assertRaises(Exception):
            n.title = "y"  # type: ignore[misc]

    def test_long_distill_result_dataclass(self) -> None:
        r = LongDistillResult(ok=True, notes=[], raw_responses=[])
        self.assertTrue(r.ok)


if __name__ == "__main__":
    unittest.main()
