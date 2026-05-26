import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fde_brain.distill_local import LocalDistillResult, LocalPromotedNote
from tools.fde_brain.ingest import main
from tools.fde_brain.paths import WorkspacePaths
from tools.fde_brain.preflight import CheckResult


def _setup_workspace(root: Path) -> WorkspacePaths:
    paths = WorkspacePaths(root)
    paths.ensure_directories()
    paths.agent_protocol.write_text("# protocol\n", encoding="utf-8")
    paths.runbook.write_text("# runbook\n", encoding="utf-8")
    paths.claude_entrypoint.write_text("# claude\n", encoding="utf-8")
    paths.codex_entrypoint.write_text("# codex\n", encoding="utf-8")
    return paths


def _all_ok_preflight(*_args, **_kwargs) -> list[CheckResult]:
    return [
        CheckResult("Claude Code", True, "ok"),
        CheckResult("Codex CLI", True, "ok"),
        CheckResult("Ollama", True, "ok"),
        CheckResult("GLM-OCR model", True, "ok"),
        CheckResult("Graphify", True, "ok"),
        CheckResult("Git", True, "ok"),
    ]


class IngestIntegrationTests(unittest.TestCase):
    @patch("tools.fde_brain.ingest.distill_normalized_sections")
    @patch("tools.fde_brain.ingest.run_preflight", side_effect=_all_ok_preflight)
    def test_dry_run_does_not_move_or_write_pending_files(self, _pf, distill_mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _setup_workspace(root)
            pending = paths.pending / "note.md"
            pending.write_text("# Hello\nBody.", encoding="utf-8")

            exit_code = main(["--root", str(root), "--dry-run"])

            self.assertEqual(0, exit_code)
            self.assertTrue(pending.exists())
            raw_markdown = paths.raw_for("markdown")
            self.assertFalse(raw_markdown.exists())
            self.assertFalse(paths.registry_path.exists())
            self.assertEqual([], [p for p in paths.logs_runs.iterdir() if p.name != ".gitkeep"])
            distill_mock.assert_not_called()

    @patch("tools.fde_brain.ingest.run_preflight", side_effect=_all_ok_preflight)
    def test_preflight_uses_configured_distill_model(self, pf_mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_workspace(root)

            exit_code = main(["--root", str(root), "--no-commit", "--distill-model", "custom:model"])

            self.assertEqual(0, exit_code)
            pf_mock.assert_called_once_with(distill_model="custom:model")

    @patch("tools.fde_brain.ingest.distill_normalized_sections")
    @patch("tools.fde_brain.ingest.run_preflight", side_effect=_all_ok_preflight)
    def test_markdown_passes_through_without_promotion(self, _pf, distill_mock) -> None:
        distill_mock.return_value = LocalDistillResult(ok=True, notes=[])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _setup_workspace(root)
            (paths.pending / "note.md").write_text("# Hello\nBody.", encoding="utf-8")

            exit_code = main(["--root", str(root), "--no-commit"])

            self.assertEqual(0, exit_code)
            self.assertFalse((paths.pending / "note.md").exists())
            raw_files = list(paths.raw_for("markdown").iterdir())
            raw_files = [p for p in raw_files if p.name != ".gitkeep"]
            self.assertEqual(1, len(raw_files))
            self.assertTrue(raw_files[0].name.endswith("note.md"))
            self.assertTrue((paths.normalized_for("markdown") / "note" / "manifest.json").exists())
            self.assertTrue((paths.normalized_for("markdown") / "note" / "sections" / "001-hello.md").exists())
            self.assertTrue(paths.registry_path.exists())
            data = json.loads(paths.registry_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(data["entries"]))
            self.assertGreaterEqual(len(data["entries"][0]["normalized_paths"]), 3)
            self.assertEqual([], list(paths.fde_brain.glob("*.md")))
            self.assertTrue(paths.source_graph_stale.exists())
            log_files = list(paths.logs_runs.glob("*.json"))
            self.assertEqual(1, len(log_files))

    @patch("tools.fde_brain.ingest.distill_normalized_sections")
    @patch("tools.fde_brain.ingest.run_preflight", side_effect=_all_ok_preflight)
    def test_markdown_with_promotion_writes_fde_brain_note(self, _pf, distill_mock) -> None:
        promoted_md = (
            "---\ntype: concept\nstatus: evergreen\naliases:\n  - Hello\n"
            "tags:\n  - demo\nsources:\n  - raw_path: x\n    normalized_path: y\n"
            "created: 2026-05-22\nupdated: 2026-05-22\n---\n\n# Hello\n\n"
            "## Summary\n\nSummary.\n\n## Core Idea\n\nCore.\n\n## Practical Use\n\nUse.\n\n## Related\n\n- \n"
        )
        distill_mock.return_value = LocalDistillResult(
            ok=True,
            notes=[
                LocalPromotedNote(
                    title="Hello",
                    type="concept",
                    content=promoted_md,
                    source_section=Path("x"),
                    confidence=0.9,
                )
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _setup_workspace(root)
            (paths.pending / "hello.md").write_text("# Hello\nBody.", encoding="utf-8")

            exit_code = main(["--root", str(root), "--no-commit"])

            self.assertEqual(0, exit_code)
            promoted = paths.fde_brain / "Hello.md"
            self.assertTrue(promoted.exists())
            self.assertEqual(promoted_md, promoted.read_text(encoding="utf-8"))
            self.assertTrue(paths.brain_graph_stale.exists())

    @patch("tools.fde_brain.ingest.distill_normalized_sections")
    @patch("tools.fde_brain.ingest.run_preflight", side_effect=_all_ok_preflight)
    def test_unknown_extension_routes_to_review(self, _pf, distill_mock) -> None:
        distill_mock.return_value = LocalDistillResult(ok=True, notes=[])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _setup_workspace(root)
            (paths.pending / "weird.xyz").write_bytes(b"binary blob")

            exit_code = main(["--root", str(root), "--no-commit"])

            self.assertEqual(0, exit_code)
            review_files = list((paths.review / "needs-human").glob("*.md"))
            self.assertEqual(1, len(review_files))
            distill_mock.assert_not_called()

    @patch("tools.fde_brain.ingest.distill_normalized_sections")
    @patch("tools.fde_brain.ingest.normalize_source")
    @patch("tools.fde_brain.ingest.run_preflight", side_effect=_all_ok_preflight)
    def test_pdf_uses_local_section_distill(
        self, _pf, normalize_mock, distill_mock
    ) -> None:
        from tools.fde_brain.normalize import NormalizedOutput

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _setup_workspace(root)
            pdf_pending = paths.pending / "book.pdf"
            pdf_pending.write_bytes(b"%PDF-1.4 stub")

            manifest_path = paths.normalized_for("pdf") / "book" / "manifest.json"
            section_path = paths.normalized_for("pdf") / "book" / "sections" / "001-book.md"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            section_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("{}", encoding="utf-8")
            section_path.write_text("---\n---\n\n# stub\n", encoding="utf-8")
            normalize_mock.return_value = NormalizedOutput(
                ok=True,
                output_path=manifest_path,
                routed_to="normalized",
                parser="pypdf",
                manifest_path=manifest_path,
                section_paths=[section_path],
                quality_report_path=paths.normalized_for("pdf") / "book" / "quality-report.json",
                package_dir=paths.normalized_for("pdf") / "book",
            )

            notes = [
                LocalPromotedNote(title="Overview", type="overview", content="---\ntype: overview\n---\n\n# Overview\n", source_section=section_path, confidence=0.9),
                LocalPromotedNote(title="Chapter Key Idea", type="concept", content="---\ntype: concept\n---\n\n# Chapter Key Idea\n", source_section=section_path, confidence=0.9),
                LocalPromotedNote(title="Cool Pattern", type="pattern", content="---\ntype: pattern\n---\n\n# Cool Pattern\n", source_section=section_path, confidence=0.9),
            ]
            distill_mock.return_value = LocalDistillResult(ok=True, notes=notes, raw_responses=[])

            exit_code = main(["--root", str(root), "--no-commit"])

            self.assertEqual(0, exit_code)
            distill_mock.assert_called_once()
            brain_notes = sorted(p.name for p in paths.fde_brain.glob("*.md"))
            self.assertEqual(["Chapter-Key-Idea.md", "Cool-Pattern.md", "Overview.md"], brain_notes)

            registry = json.loads(paths.registry_path.read_text(encoding="utf-8"))
            promoted = registry["entries"][0]["promoted_to"]
            self.assertEqual(3, len(promoted))

    @patch("tools.fde_brain.ingest.distill_normalized_sections")
    @patch("tools.fde_brain.ingest.normalize_source")
    @patch("tools.fde_brain.ingest.run_preflight", side_effect=_all_ok_preflight)
    def test_normalized_source_without_sections_does_not_distill(
        self, _pf, normalize_mock, distill_mock
    ) -> None:
        from tools.fde_brain.normalize import NormalizedOutput

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _setup_workspace(root)
            pdf_pending = paths.pending / "paper.pdf"
            pdf_pending.write_bytes(b"%PDF-1.4 stub")

            normalized_path = paths.normalized_for("pdf") / "paper.md"
            normalized_path.parent.mkdir(parents=True, exist_ok=True)
            normalized_path.write_text("---\n---\n\n# stub\n", encoding="utf-8")
            normalize_mock.return_value = NormalizedOutput(
                ok=True, output_path=normalized_path, routed_to="normalized", parser="pypdf"
            )

            exit_code = main(["--root", str(root), "--no-commit"])

            self.assertEqual(0, exit_code)
            distill_mock.assert_not_called()

    @patch("tools.fde_brain.ingest.run_preflight", side_effect=_all_ok_preflight)
    def test_empty_pending_no_changes(self, _pf) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_workspace(root)

            exit_code = main(["--root", str(root), "--no-commit"])

            self.assertEqual(0, exit_code)

    @patch("tools.fde_brain.ingest.run_preflight")
    def test_preflight_failure_returns_one(self, pf_mock) -> None:
        pf_mock.return_value = [CheckResult("Graphify", False, "missing")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_workspace(root)

            exit_code = main(["--root", str(root), "--no-commit"])

            self.assertEqual(1, exit_code)


if __name__ == "__main__":
    unittest.main()
