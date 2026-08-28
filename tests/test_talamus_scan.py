import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from talamus.errors import TalamusError
from talamus.jobs import JobRecord, JobStore
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.scan import (
    ScanPlan,
    ScanSecretsDetected,
    build_plan,
    code_digest,
    execute_plan,
    format_plan,
    scan_job_payload,
)
from talamus.store import load_notes
from tests.support import FakeLLMProvider

_REPO_ROOT = Path(__file__).resolve().parent.parent
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

try:
    import pypdf  # noqa: F401
except ImportError:
    HAS_PYPDF = False
else:
    HAS_PYPDF = True


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{_W_NS}"><w:body>{body}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def _write_pdf(path: Path, text: str) -> None:
    """Write one extractable text line without a PDF-generation dependency."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"endstream",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(content)


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

    def test_plan_flags_secret_in_extracted_docx_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_docx(root / "credentials.docx", ["api_key = docxSyntheticSecret12345"])

            plan = build_plan(root, profile="docs")

        self.assertEqual(["credentials.docx"], [entry["path"] for entry in plan.included])
        self.assertEqual({"credentials.docx"}, {flag["path"] for flag in plan.secret_flags})

    @unittest.skipUnless(HAS_PYPDF, "pypdf optional extra is not installed")
    def test_plan_flags_secret_in_extracted_pdf_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_pdf(root / "credentials.pdf", "token = pdfSyntheticSecret123456")

            plan = build_plan(root, profile="docs")

        self.assertEqual(["credentials.pdf"], [entry["path"] for entry in plan.included])
        self.assertEqual({"credentials.pdf"}, {flag["path"] for flag in plan.secret_flags})

    def test_binary_document_prose_without_assignment_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_docx(root / "policy.docx", ["How to rotate an API key safely."])

            plan = build_plan(root, profile="docs")

        self.assertEqual([], plan.secret_flags)

    @unittest.skipUnless(HAS_PYPDF, "pypdf optional extra is not installed")
    def test_pdf_prose_without_assignment_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_pdf(root / "policy.pdf", "How to rotate an API key safely.")

            plan = build_plan(root, profile="docs")

        self.assertEqual([], plan.secret_flags)

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
            report = execute_plan(paths, plan, StaticRouter(llm), allow_secrets=True)
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
            report = execute_plan(paths, plan, StaticRouter(llm), allow_secrets=True)
            self.assertEqual(report["state"], "completed")
            self.assertEqual(len(report["failed"]), len(plan.included))

    def test_execute_rejects_flagged_plan_before_first_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            _fixture_repo(Path(repo))
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            plan = build_plan(Path(repo), profile="docs")
            llm = FakeLLMProvider([])

            with self.assertRaises(ScanSecretsDetected):
                execute_plan(paths, plan, StaticRouter(llm))

        self.assertEqual([], llm.prompts)

    def test_execute_rechecks_every_source_before_first_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            root = Path(repo)
            (root / "a.md").write_text("# Safe first file", encoding="utf-8")
            second = root / "z.md"
            second.write_text("# Safe second file", encoding="utf-8")
            plan = build_plan(root, profile="docs")
            second.write_text("token = changedAfterPlanning12345", encoding="utf-8")
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            llm = FakeLLMProvider([])

            with self.assertRaises(ScanSecretsDetected):
                execute_plan(paths, plan, StaticRouter(llm))

        self.assertEqual([], llm.prompts)

    def test_execute_redacts_extracted_docx_and_audits_override_safely(self) -> None:
        synthetic_value = "docxSyntheticSecret12345"
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            root = Path(repo)
            _write_docx(root / "credentials.docx", [f"api_key = {synthetic_value}"])
            plan = build_plan(root, profile="docs")
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            llm = FakeLLMProvider([_note_json("Documento redatto")])

            report = execute_plan(
                paths,
                plan,
                StaticRouter(llm),
                allow_secrets=True,
            )
            log = JobStore(paths).read_log(report["job_id"])

        self.assertEqual("completed", report["state"])
        self.assertEqual(1, len(llm.prompts))
        self.assertIn("[REDACTED:generic-assignment]", llm.prompts[0])
        self.assertNotIn(synthetic_value, llm.prompts[0])
        self.assertIn("--allow-secrets", log)
        self.assertIn("credentials.docx", log)
        self.assertNotIn(synthetic_value, log)

    @unittest.skipUnless(HAS_PYPDF, "pypdf optional extra is not installed")
    def test_execute_redacts_extracted_pdf_text(self) -> None:
        synthetic_value = "pdfSyntheticSecret123456"
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            root = Path(repo)
            _write_pdf(root / "credentials.pdf", f"token = {synthetic_value}")
            plan = build_plan(root, profile="docs")
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            llm = FakeLLMProvider([_note_json("PDF redatto")])

            report = execute_plan(
                paths,
                plan,
                StaticRouter(llm),
                allow_secrets=True,
            )

        self.assertEqual("completed", report["state"])
        self.assertIn("[REDACTED:generic-assignment]", llm.prompts[0])
        self.assertNotIn(synthetic_value, llm.prompts[0])

    def test_execute_rejects_traversal_in_persisted_plan(self) -> None:
        with tempfile.TemporaryDirectory() as parent, tempfile.TemporaryDirectory() as brain:
            parent_path = Path(parent)
            root = parent_path / "repo"
            root.mkdir()
            outside = parent_path / "outside.md"
            outside.write_text("private material outside the repository", encoding="utf-8")
            plan = ScanPlan(
                root=str(root),
                profile="docs",
                included=[{"path": "../outside.md", "category": "docs", "bytes": 39}],
            )
            paths = TalamusPaths(Path(brain))
            paths.ensure_directories()
            llm = FakeLLMProvider([])

            with self.assertRaisesRegex(TalamusError, "missing or unsafe"):
                execute_plan(paths, plan, StaticRouter(llm))

        self.assertEqual([], llm.prompts)

    def test_scan_plan_excludes_a_symlinked_file(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as outside:
            (Path(repo) / "readme.md").write_text("# Real\ncontent", encoding="utf-8")
            outside_file = Path(outside) / "secret.md"
            outside_file.write_text("SECRET OUTSIDE THE REPO", encoding="utf-8")
            try:
                os.symlink(outside_file, Path(repo) / "evil.md")
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
            self.assertIs(jobs[0].payload.get("allow_secrets"), True)
            self.assertIn("jobs resume", out.getvalue())

    def test_resume_passes_persisted_secret_override(self) -> None:
        from talamus.cli.pipeline import _run_scan_job

        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as brain:
            plan = build_plan(Path(repo), profile="docs")
            record = JobRecord(
                job_id="scan-test",
                kind="scan",
                payload=scan_job_payload(plan, allow_secrets=True),
            )
            report = {
                "job_id": record.job_id,
                "state": "completed",
                "notes_written": 0,
                "files": 0,
                "failed": [],
            }
            with (
                mock.patch("talamus.cli.pipeline._router_for", return_value=mock.Mock()),
                mock.patch("talamus.cli.pipeline.execute_plan", return_value=report) as run,
                redirect_stdout(io.StringIO()),
            ):
                code = _run_scan_job(Path(brain), record)

        self.assertEqual(0, code)
        self.assertIs(run.call_args.kwargs["allow_secrets"], True)


if __name__ == "__main__":
    unittest.main()
