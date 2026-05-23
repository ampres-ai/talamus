import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fde_brain.distill_v3 import (
    DistillV3Result,
    PromotedNote,
    distill_v3,
)
from tools.fde_brain.paths import WorkspacePaths


NORMALIZED_BODY = """---
source-path: AI Space/raw/pdf/2026-05-22-book.pdf
source-type: pdf
source-hash: sha256:abc
captured-at: 2026-05-22T12:00:00+00:00
parser: pypdf
parser-confidence: 1.0
---

# book

## Chapter 1: Foundations

_Pages 1–10_

### Subsection 1a
Foundations text body.

### Subsection 1b
More foundation text.

## Chapter 2: Patterns

_Pages 11–25_

Patterns text.
"""


def _proc(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["claude", "-p"], returncode=returncode, stdout=stdout, stderr=stderr)


def _setup_normalized(root: Path) -> tuple[Path, WorkspacePaths]:
    paths = WorkspacePaths(root)
    paths.ensure_directories()
    normalized = paths.normalized_for("pdf") / "book.md"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalized.write_text(NORMALIZED_BODY, encoding="utf-8")
    return normalized, paths


def _chunk_response(notes: list[dict]) -> str:
    return json.dumps({"notes": notes})


class DistillV3Tests(unittest.TestCase):
    @patch("tools.fde_brain.distill_v3.subprocess.run")
    def test_multi_chunk_plus_overview(self, run_mock) -> None:
        ch1 = _chunk_response([
            {"title": "Foundations Key Idea", "type": "concept",
             "body": "Body for foundations.", "tags": ["a"],
             "source_anchors": ["AI Space/normalized/pdf/book.md#chapter-1-foundations"]},
        ])
        ch2 = _chunk_response([
            {"title": "Useful Pattern", "type": "pattern",
             "body": "Pattern body.", "tags": ["pattern"],
             "source_anchors": ["AI Space/normalized/pdf/book.md#chapter-2-patterns"]},
        ])
        overview = _chunk_response([
            {"title": "book Overview", "type": "overview",
             "body": "See [[Foundations Key Idea]] and [[Useful Pattern]].",
             "tags": ["overview"],
             "source_anchors": ["AI Space/normalized/pdf/book.md"]},
        ])
        run_mock.side_effect = [_proc(ch1), _proc(ch2), _proc(overview)]
        with tempfile.TemporaryDirectory() as tmp:
            normalized, paths = _setup_normalized(Path(tmp))
            result = distill_v3(normalized, paths, run_id="run-1")

        self.assertTrue(result.ok, msg=result.error)
        types = sorted({n.type for n in result.notes})
        self.assertEqual(["concept", "overview", "pattern"], types)
        self.assertEqual(3, len(result.notes))
        for note in result.notes:
            self.assertTrue(note.content.startswith("---\n"))
            self.assertIn("ingestion-run: run-1", note.content)
        self.assertEqual(2, result.audit["chunks_processed"])
        self.assertEqual(3, result.audit["notes_total"])

    @patch("tools.fde_brain.distill_v3.subprocess.run")
    def test_fusion_of_multiple_source_anchors(self, run_mock) -> None:
        fused = _chunk_response([
            {"title": "Cross Concept", "type": "concept",
             "body": "Fused body.", "tags": [],
             "source_anchors": [
                 "AI Space/normalized/pdf/book.md#chapter-1-foundations",
                 "AI Space/normalized/pdf/book.md#chapter-2-patterns",
             ]},
        ])
        run_mock.side_effect = [_proc(fused), _proc(_chunk_response([])), _proc(_chunk_response([]))]
        with tempfile.TemporaryDirectory() as tmp:
            normalized, paths = _setup_normalized(Path(tmp))
            result = distill_v3(normalized, paths, run_id="x")

        cross = next(n for n in result.notes if n.title == "Cross Concept")
        self.assertEqual(2, len(cross.source_anchors))
        self.assertIn("#chapter-1-foundations", "\n".join(cross.source_anchors))
        self.assertIn("#chapter-2-patterns", "\n".join(cross.source_anchors))

    @patch("tools.fde_brain.distill_v3.subprocess.run")
    def test_wikilink_validation_drops_unresolved(self, run_mock) -> None:
        first = _chunk_response([
            {"title": "Existing Note", "type": "concept",
             "body": "Refers to [[Bogus Reference]] and [[Existing Note|aliased]]. Also [[Real Other Note]].",
             "tags": [],
             "source_anchors": ["AI Space/normalized/pdf/book.md#chapter-1-foundations"]},
            {"title": "Real Other Note", "type": "concept", "body": "Body.", "tags": [],
             "source_anchors": ["AI Space/normalized/pdf/book.md#chapter-1-foundations"]},
        ])
        run_mock.side_effect = [_proc(first), _proc(_chunk_response([])), _proc(_chunk_response([]))]
        with tempfile.TemporaryDirectory() as tmp:
            normalized, paths = _setup_normalized(Path(tmp))
            result = distill_v3(normalized, paths, run_id="x")

        existing = next(n for n in result.notes if n.title == "Existing Note")
        self.assertNotIn("[[Bogus Reference]]", existing.content)
        self.assertIn("Bogus Reference", existing.content)
        self.assertIn("[[Existing Note|aliased]]", existing.content)
        self.assertIn("[[Real Other Note]]", existing.content)
        self.assertEqual(1, len(result.audit["wikilinks_dropped"]))
        self.assertIn("Bogus Reference", result.audit["wikilinks_dropped"][0]["dropped"])

    @patch("tools.fde_brain.distill_v3.subprocess.run")
    def test_fenced_json_response_is_parsed(self, run_mock) -> None:
        fenced = "```json\n" + _chunk_response([
            {"title": "Foo", "type": "concept", "body": "Bar", "tags": [],
             "source_anchors": ["AI Space/normalized/pdf/book.md#chapter-1-foundations"]},
        ]) + "\n```"
        run_mock.side_effect = [_proc(fenced), _proc(_chunk_response([])), _proc(_chunk_response([]))]
        with tempfile.TemporaryDirectory() as tmp:
            normalized, paths = _setup_normalized(Path(tmp))
            result = distill_v3(normalized, paths, run_id="x")

        self.assertTrue(result.ok)
        self.assertTrue(any(n.title == "Foo" for n in result.notes))

    @patch("tools.fde_brain.distill_v3.subprocess.run")
    def test_malformed_json_returns_error(self, run_mock) -> None:
        run_mock.return_value = _proc("not json at all")
        with tempfile.TemporaryDirectory() as tmp:
            normalized, paths = _setup_normalized(Path(tmp))
            result = distill_v3(normalized, paths, run_id="x")

        self.assertFalse(result.ok)
        self.assertIn("json", (result.error or "").lower())

    @patch("tools.fde_brain.distill_v3.subprocess.run")
    def test_timeout_returns_error(self, run_mock) -> None:
        run_mock.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=5)
        with tempfile.TemporaryDirectory() as tmp:
            normalized, paths = _setup_normalized(Path(tmp))
            result = distill_v3(normalized, paths, run_id="x", timeout_sec=5)

        self.assertFalse(result.ok)
        self.assertIn("timeout", (result.error or "").lower())

    @patch("tools.fde_brain.distill_v3.subprocess.run")
    def test_audit_log_written_to_logs_decisions(self, run_mock) -> None:
        run_mock.side_effect = [
            _proc(_chunk_response([])),
            _proc(_chunk_response([])),
            _proc(_chunk_response([])),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            normalized, paths = _setup_normalized(Path(tmp))
            result = distill_v3(normalized, paths, run_id="audit-test")
            audits = list(paths.logs_decisions.glob("*audit-test*.json"))
            self.assertTrue(result.ok)
            self.assertEqual(1, len(audits))
            data = json.loads(audits[0].read_text(encoding="utf-8"))
            self.assertEqual("audit-test", data["run_id"])
            self.assertEqual(2, data["chunks_processed"])

    def test_promoted_note_frozen(self) -> None:
        n = PromotedNote(title="t", type="concept", content="---\n---\n", source_anchors=[])
        with self.assertRaises(Exception):
            n.title = "other"  # type: ignore[misc]

    def test_result_dataclass(self) -> None:
        r = DistillV3Result(ok=True)
        self.assertTrue(r.ok)
        self.assertEqual([], r.notes)


if __name__ == "__main__":
    unittest.main()
