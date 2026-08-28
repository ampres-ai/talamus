import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from talamus.jobs import JobStore
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.scan import build_plan
from talamus.services.scan import preview_scan, run_scan
from talamus.store import load_notes
from tests.support import FakeLLMProvider
from tests.test_talamus_scan import _fixture_repo, _note_json, _write_docx, _write_pdf


class TalamusScanServiceTests(unittest.TestCase):
    def test_preview_scan_builds_plan_without_notes(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()

            result = preview_scan(brain, repo, profile="docs")

            notes = load_notes(paths)

        self.assertTrue(result.success, result.message)
        self.assertEqual("scan_preview_ready", result.code)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertGreater(result.data.files, 0)
        self.assertEqual(result.data.est_llm_calls, result.data.files)
        self.assertEqual([], notes)

    def test_run_scan_without_confirmation_makes_no_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            llm = FakeLLMProvider([])

            result = run_scan(brain, repo, StaticRouter(llm), profile="docs", confirmed=False)

            notes = load_notes(paths)

        self.assertTrue(result.success, result.message)
        self.assertEqual("scan_confirmation_required", result.code)
        self.assertEqual([], llm.prompts)  # not a single LLM call without consent
        self.assertEqual([], notes)

    def test_run_scan_blocks_secrets_without_llm_calls(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            llm = FakeLLMProvider([])

            result = run_scan(
                brain,
                repo,
                StaticRouter(llm),
                profile="docs",
                confirmed=True,
                allow_secrets=False,
            )

        self.assertFalse(result.success)
        self.assertEqual("scan_secrets_blocked", result.code)
        self.assertEqual([], llm.prompts)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertIn("config.md", result.data.secret_files)

    def test_run_scan_blocks_secret_in_docx_without_llm_calls(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _write_docx(
                Path(repo) / "credentials.docx",
                ["client_secret = docxSyntheticSecret12345"],
            )
            llm = FakeLLMProvider([])

            result = run_scan(
                brain,
                repo,
                StaticRouter(llm),
                profile="docs",
                confirmed=True,
                allow_secrets=False,
            )

        self.assertFalse(result.success)
        self.assertEqual("scan_secrets_blocked", result.code)
        self.assertEqual([], llm.prompts)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(("credentials.docx",), result.data.secret_files)

    def test_preview_pdf_without_extra_returns_actionable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _write_pdf(Path(repo) / "document.pdf", "Safe document")

            with mock.patch.dict(sys.modules, {"pypdf": None}):
                result = preview_scan(brain, repo, profile="docs")

        self.assertFalse(result.success)
        self.assertEqual("scan_failed", result.code)
        self.assertIn("pip install talamus[pdf]", result.message)

    def test_run_pdf_without_extra_fails_before_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _write_pdf(Path(repo) / "document.pdf", "Safe document")
            llm = FakeLLMProvider([])

            with mock.patch.dict(sys.modules, {"pypdf": None}):
                result = run_scan(
                    brain,
                    repo,
                    StaticRouter(llm),
                    profile="docs",
                    confirmed=True,
                )

        self.assertFalse(result.success)
        self.assertEqual("scan_failed", result.code)
        self.assertIn("pip install talamus[pdf]", result.message)
        self.assertEqual([], llm.prompts)

    def test_run_scan_background_queues_job_without_llm_calls(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            llm = FakeLLMProvider([])

            result = run_scan(
                brain,
                repo,
                StaticRouter(llm),
                profile="docs",
                background=True,
                allow_secrets=True,
            )

            jobs = JobStore(paths).list()

        self.assertTrue(result.success, result.message)
        self.assertEqual("scan_queued", result.code)
        self.assertEqual([], llm.prompts)
        self.assertEqual(1, len(jobs))
        self.assertEqual("queued", jobs[0].state)
        self.assertIs(jobs[0].payload.get("allow_secrets"), True)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(jobs[0].job_id, result.data.job_id)

    def test_run_scan_confirmed_executes_plan(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            plan = build_plan(Path(repo), profile="docs")
            llm = FakeLLMProvider([_note_json(f"Concetto {i}") for i in range(len(plan.included))])

            result = run_scan(
                brain,
                repo,
                StaticRouter(llm),
                profile="docs",
                confirmed=True,
                allow_secrets=True,
            )

            notes = load_notes(paths)

        self.assertTrue(result.success, result.message)
        self.assertEqual("scan_completed", result.code)
        self.assertEqual(len(plan.included), len(llm.prompts))
        self.assertTrue(notes)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual("completed", result.data.state)
        self.assertEqual(len(plan.included), result.data.files)


if __name__ == "__main__":
    unittest.main()
