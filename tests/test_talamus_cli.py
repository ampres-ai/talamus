import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from talamus.cli import main
from talamus.config import load_config
from talamus.paths import TalamusPaths
from tests.support import FakeLLMProvider


class TalamusCliTests(unittest.TestCase):
    def test_init_creates_new_layout_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                code = main(["init", "--root", tmp])

            self.assertEqual(0, code)
            self.assertTrue((Path(tmp) / "talamus.json").is_file())
            self.assertTrue((Path(tmp) / "notes").is_dir())
            self.assertTrue((Path(tmp) / ".talamus" / "cache").is_dir())

    def test_status_and_doctor_return_zero_after_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
                self.assertEqual(0, main(["status", "--root", tmp]))
                self.assertEqual(0, main(["doctor", "--root", tmp]))

    def test_status_rejects_required_directory_replaced_by_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            raw_path = Path(tmp) / ".talamus" / "raw"
            shutil.rmtree(raw_path)
            raw_path.write_text("not a directory", encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                code = main(["status", "--root", tmp])

            self.assertEqual(1, code)
            self.assertIn("not a directory", stderr.getvalue())

    def test_doctor_reports_malformed_config_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            (Path(tmp) / "talamus.json").write_text("{invalid json", encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                code = main(["doctor", "--root", tmp])

            self.assertEqual(1, code)
            self.assertIn("config error", stderr.getvalue())

    def test_ensure_utf8_output_tolerates_non_reconfigurable_stream(self) -> None:
        from talamus.cli import _ensure_utf8_output

        with redirect_stdout(io.StringIO()):
            _ensure_utf8_output()  # non deve sollevare eccezioni

    def test_ingest_then_ask_with_injected_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            source = Path(tmp) / "rag.md"
            source.write_text("# RAG\nRAG collega il modello a fonti esterne.", encoding="utf-8")
            extract_llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Retrieval-Augmented Generation",
                                "aliases": ["RAG"],
                                "retrieval_text": "rag fonti esterne",
                                "summary": "RAG collega a fonti.",
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            }
                        ]
                    )
                ]
            )
            answer_llm = FakeLLMProvider(["RAG [1]."])

            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["ingest", str(source), "--root", tmp], llm=extract_llm))
                self.assertEqual(
                    0, main(["ask", "Come collego fonti esterne?", "--root", tmp], llm=answer_llm)
                )

    def test_search_read_recall_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            source = Path(tmp) / "rag.md"
            source.write_text("# RAG\nRAG collega il modello a fonti esterne.", encoding="utf-8")
            extract_llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Retrieval-Augmented Generation",
                                "aliases": ["RAG"],
                                "retrieval_text": "rag fonti esterne",
                                "summary": "RAG collega a fonti.",
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            }
                        ]
                    )
                ]
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["ingest", str(source), "--root", tmp], llm=extract_llm))

            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["search", "fonti esterne", "--root", tmp]))
                self.assertEqual(0, main(["read", "Retrieval-Augmented Generation", "--root", tmp]))
                self.assertEqual(0, main(["recall", "come collego fonti esterne?", "--root", tmp]))
            self.assertIn("Retrieval-Augmented Generation", out.getvalue())

    def test_remember_command_captures_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            transcript = Path(tmp) / "t.md"
            transcript.write_text("x" * 500, encoding="utf-8")
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Sessione",
                                "retrieval_text": "x",
                                "summary": "s",
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            }
                        ]
                    )
                ]
            )
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(
                    0, main(["remember", "--transcript", str(transcript), "--root", tmp], llm=llm)
                )
            self.assertIn("ricordate", out.getvalue())

    def test_neighbors_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            source = Path(tmp) / "d.md"
            source.write_text("# D\nAlpha e Beta.", encoding="utf-8")
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Alpha",
                                "retrieval_text": "alpha",
                                "summary": "a",
                                "body_sections": {"definizione": "Alpha usa Beta."},
                                "proposed_links": [
                                    {"anchor": "Beta", "target": "Beta", "reason": "x"}
                                ],
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            },
                            {
                                "title": "Beta",
                                "retrieval_text": "beta",
                                "summary": "b",
                                "supported_claims": ["y"],
                                "confidence": 0.9,
                            },
                        ]
                    )
                ]
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["ingest", str(source), "--root", tmp], llm=llm))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["neighbors", "Alpha", "--root", tmp]))
            self.assertIn("Beta", out.getvalue())

    def test_read_missing_note_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            with redirect_stderr(io.StringIO()):
                self.assertEqual(1, main(["read", "Inesistente", "--root", tmp]))

    def test_no_args_shows_panel(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, main([]))
        self.assertIn("Talamus", out.getvalue())

    def test_quickstart_lists_commands(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, main(["quickstart"]))
        self.assertIn("talamus init", out.getvalue())

    def test_search_json_output_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["search", "x", "--root", tmp, "--json"]))
            self.assertIsInstance(json.loads(out.getvalue()), list)

    def test_init_with_engine_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp, "--engine", "ollama"]))
            cfg = load_config(TalamusPaths(Path(tmp)).config_path)
            self.assertEqual("ollama", cfg.llm_provider)

    def test_doctor_reports_engine_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["doctor", "--root", tmp]))
            text = out.getvalue()
            self.assertIn("llm:", text)
            self.assertIn("cache:", text)

    def test_where_reports_brain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", tmp]))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["where", "--root", tmp]))
            self.assertIn("brain", out.getvalue())

    def test_export_import_roundtrip(self) -> None:
        from talamus.store import load_notes

        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", "--root", a]))
            source = Path(a) / "doc.md"
            source.write_text("# Doc\nAlpha.", encoding="utf-8")
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Alpha",
                                "retrieval_text": "a",
                                "summary": "a",
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            }
                        ]
                    )
                ]
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["ingest", str(source), "--root", a], llm=llm))
            zip_path = str(Path(b) / "brain.zip")
            dest = str(Path(b) / "restored")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["export", zip_path, "--root", a]))
                self.assertEqual(0, main(["import", zip_path, "--root", dest]))
            self.assertEqual(1, len(load_notes(TalamusPaths(Path(dest)))))

    def test_resolve_root_precedence(self) -> None:
        from talamus.cli import _resolve_root

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(Path(tmp).resolve(), _resolve_root(tmp, "x", True))

    def test_completion_prints_script(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, main(["completion", "bash"]))
        self.assertIn("complete -F", out.getvalue())

    def test_demo_creates_searchable_brain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["demo", "--root", tmp]))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["search", "embedding", "--root", tmp]))
            self.assertIn("Embedding", out.getvalue())


if __name__ == "__main__":
    unittest.main()
