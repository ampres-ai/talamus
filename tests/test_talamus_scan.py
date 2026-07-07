import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.scan import build_plan, code_digest, execute_plan, format_plan
from talamus.store import load_notes
from tests.support import FakeLLMProvider

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _fixture_repo(root: Path) -> None:
    (root / ".gitignore").write_text("ignorata/\n*.log\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\nUn progetto di esempio con scopo chiaro.", "utf-8")
    (root / "src").mkdir()
    (root / "src" / "core.py").write_text(
        '"""Modulo core del progetto demo."""\n\n\ndef api_pubblica(x):\n'
        '    """Fa la cosa principale."""\n    return x\n\n\ndef _privata():\n    pass\n',
        encoding="utf-8",
    )
    (root / "node_modules").mkdir()
    (root / "node_modules" / "lib.js").write_text("function x(){}", encoding="utf-8")
    (root / "ignorata").mkdir()
    (root / "ignorata" / "doc.md").write_text("# Da ignorare\ncontenuto " * 10, encoding="utf-8")
    (root / "debug.log").write_text("log riga", encoding="utf-8")
    (root / ".env").write_text("API_KEY=segretissimo123456789", encoding="utf-8")
    (root / "package-lock.json").write_text("{}", encoding="utf-8")
    (root / "config.md").write_text(
        "# Config\nLa chiave è api_key = abcdefghij1234567890 nel file.", encoding="utf-8"
    )


def _note_json(title: str) -> str:
    return json.dumps(
        [
            {
                "title": title,
                "retrieval_text": title.lower(),
                "summary": f"{title}.",
                "supported_claims": ["x"],
                "confidence": 0.9,
            }
        ]
    )


class BuildPlanTests(unittest.TestCase):
    def test_plan_includes_docs_and_code_excludes_vendor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _fixture_repo(Path(tmp))
            plan = build_plan(Path(tmp), profile="all")
            included = {e["path"] for e in plan.included}
            self.assertIn("README.md", included)
            self.assertIn("src/core.py", included)
            self.assertFalse(any("node_modules" in p for p in included))
            reasons = {e["path"]: e["reason"] for e in plan.excluded}
            self.assertEqual(reasons.get("ignorata/"), ".gitignore")  # pruned dir, recorded
            self.assertFalse(any(p.startswith("ignorata/d") for p in reasons))  # not walked
            self.assertEqual(reasons.get("debug.log"), ".gitignore")
            self.assertEqual(reasons.get(".env"), "secret-like file")
            self.assertEqual(reasons.get("package-lock.json"), "lockfile")
            self.assertGreater(plan.est_tokens, 0)
            self.assertEqual(plan.est_llm_calls, len(plan.included))

    def test_plan_flags_content_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _fixture_repo(Path(tmp))
            plan = build_plan(Path(tmp), profile="docs")
            flagged = {f["path"] for f in plan.secret_flags}
            self.assertIn("config.md", flagged)

    def test_profile_docs_skips_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _fixture_repo(Path(tmp))
            plan = build_plan(Path(tmp), profile="docs")
            self.assertFalse(any(e["category"] == "code" for e in plan.included))

    def test_dry_run_on_this_repository(self) -> None:
        """M3 gate: scanning this repo in dry-run is safe and sane."""
        plan = build_plan(_REPO_ROOT, profile="docs")
        included = {e["path"] for e in plan.included}
        self.assertIn("README.md", included)
        self.assertFalse(any(p.startswith((".git/", ".talamus/")) for p in included))
        report = format_plan(plan)
        self.assertIn("Scan plan", report)

    def test_max_files_caps_inclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _fixture_repo(Path(tmp))
            plan = build_plan(Path(tmp), profile="all", max_files=1)
            self.assertEqual(len(plan.included), 1)


class CodeDigestTests(unittest.TestCase):
    def test_python_digest_keeps_public_skips_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _fixture_repo(Path(tmp))
            digest = code_digest(Path(tmp) / "src" / "core.py", "src/core.py")
            self.assertIn("Modulo: src/core.py", digest)
            self.assertIn("api_pubblica", digest)
            self.assertIn("Fa la cosa principale.", digest)
            self.assertNotIn("_privata", digest)


class ExecutePlanTests(unittest.TestCase):
    def test_execute_writes_notes_and_completes_job(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            plan = build_plan(Path(repo), profile="all")
            llm = FakeLLMProvider([_note_json(f"Concetto {i}") for i in range(len(plan.included))])
            report = execute_plan(paths, plan, StaticRouter(llm))
            self.assertEqual(report["state"], "completed")
            self.assertGreater(report["notes_written"], 0)
            self.assertEqual(report["failed"], [])
            self.assertTrue(load_notes(paths))
            # the code file went through the code-aware preamble
            self.assertTrue(any("SOURCE CODE" in p for p in llm.prompts))
            # redaction happened before the LLM saw config.md
            self.assertFalse(any("abcdefghij1234567890" in p for p in llm.prompts))

    def test_per_file_failure_recorded_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            plan = build_plan(Path(repo), profile="docs")
            llm = FakeLLMProvider(["non è json"] * len(plan.included))
            report = execute_plan(paths, plan, StaticRouter(llm))
            self.assertEqual(report["state"], "completed")
            self.assertEqual(len(report["failed"]), len(plan.included))

    def test_scan_plan_excludes_a_symlinked_file(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as outside:
            (Path(repo) / "readme.md").write_text("# Real\ncontent", encoding="utf-8")
            secret = Path(outside) / "secret.md"
            secret.write_text("SECRET OUTSIDE THE REPO", encoding="utf-8")
            try:
                os.symlink(secret, Path(repo) / "evil.md")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks need privilege on this OS")

            plan = build_plan(Path(repo), profile="docs")

            included = {e["path"] for e in plan.included}
            self.assertIn("readme.md", included)
            self.assertNotIn("evil.md", included)  # the symlink was never planned


class CliScanTests(unittest.TestCase):
    def test_dry_run_via_cli_costs_nothing(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            llm = FakeLLMProvider([])
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["scan", repo, "--dry-run", "--root", brain], llm=llm)
            self.assertEqual(0, code)
            self.assertIn("Scan plan", out.getvalue())
            self.assertEqual(llm.prompts, [])  # zero LLM calls

    def test_yes_blocked_by_secrets_without_allow(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            err = io.StringIO()
            with redirect_stderr(err):
                code = main(
                    ["scan", repo, "--yes", "--profile", "docs", "--root", brain],
                    llm=FakeLLMProvider([]),
                )
            self.assertEqual(1, code)
            self.assertIn("fix:", err.getvalue())

    def test_background_queues_resumable_job(self) -> None:
        from talamus.cli import main
        from talamus.jobs import JobStore

        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(
                    [
                        "scan", repo, "--background", "--profile", "docs",
                        "--allow-secrets", "--root", brain,
                    ],
                    llm=FakeLLMProvider([]),
                )  # fmt: skip
            self.assertEqual(0, code)
            jobs = JobStore(TalamusPaths(Path(brain))).list()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].state, "queued")
            self.assertIn("jobs resume", out.getvalue())


if __name__ == "__main__":
    unittest.main()
