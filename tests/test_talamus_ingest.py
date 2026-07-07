import json
import tempfile
import unittest
from pathlib import Path

from talamus.ingest import ingest_dir, ingest_file, ingest_text, remember_session
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.store import load_notes
from tests.support import FakeLLMProvider


class IngestTests(unittest.TestCase):
    def test_ingest_file_creates_note_raw_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            paths.ensure_directories()
            source = root / "rag.md"
            source.write_text("# RAG\nRAG collega il modello a fonti esterne.", encoding="utf-8")
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Retrieval-Augmented Generation",
                                "aliases": ["RAG"],
                                "retrieval_text": "rag fonti esterne",
                                "summary": "RAG collega a fonti esterne.",
                                "supported_claims": ["RAG collega a fonti esterne."],
                                "confidence": 0.9,
                            }
                        ]
                    )
                ]
            )

            result = ingest_file(paths, source, StaticRouter(llm))

            self.assertEqual(1, result["notes_written"])
            self.assertEqual(1, len(load_notes(paths)))
            self.assertTrue(any(paths.raw.glob("*.md")))
            self.assertTrue(any(paths.normalized.glob("*.md")))
            self.assertTrue(paths.graph_file.is_file())
            note = load_notes(paths)[0]
            self.assertTrue(note.sources[0].normalized_path.startswith(".talamus/normalized/"))

    def test_ingest_resolves_same_batch_wikilinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            paths.ensure_directories()
            source = root / "doc.md"
            source.write_text("# Doc\nRAG e Vector Store.", encoding="utf-8")
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "RAG",
                                "retrieval_text": "rag",
                                "summary": "RAG.",
                                "body_sections": {
                                    "definizione": "RAG usa un Vector Store per recuperare."
                                },
                                "proposed_links": [
                                    {
                                        "anchor": "Vector Store",
                                        "target": "Vector Store",
                                        "reason": "infra",
                                    }
                                ],
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            },
                            {
                                "title": "Vector Store",
                                "retrieval_text": "vector",
                                "summary": "VS.",
                                "body_sections": {"definizione": "Memorizza embeddings."},
                                "supported_claims": ["y"],
                                "confidence": 0.9,
                            },
                        ]
                    )
                ]
            )

            ingest_file(paths, source, StaticRouter(llm))

            rag_md = (paths.notes / "RAG.md").read_text(encoding="utf-8")
            self.assertIn("[[Vector Store", rag_md)

    def test_remember_session_compiles_when_worth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            transcript = (
                '{"role":"user","content":"come faccio X"}\n'
                '{"role":"assistant","content":"Si fa cosi perche serve Y"}'
            )
            diff = "diff --git a/x.py b/x.py\n+codice"
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Come fare X",
                                "retrieval_text": "x",
                                "summary": "Si fa cosi.",
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            }
                        ]
                    )
                ]
            )

            result = remember_session(paths, transcript, diff, StaticRouter(llm))

            self.assertFalse(result["skipped"])
            self.assertEqual(1, result["notes_written"])
            self.assertEqual(1, len(load_notes(paths)))
            self.assertTrue(any(paths.raw.glob("session-*.md")))

    def test_ingest_text_compiles_a_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Insight",
                                "retrieval_text": "x",
                                "summary": "s",
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            }
                        ]
                    )
                ]
            )

            result = ingest_text(paths, "Abbiamo deciso X perche Y.", StaticRouter(llm))

            self.assertEqual(1, result["notes_written"])
            self.assertEqual(1, len(load_notes(paths)))

    def test_ingest_dir_records_failures_without_aborting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            paths.ensure_directories()
            src = root / "src"
            src.mkdir()
            (src / "good.md").write_text("# Buono\nContenuto valido.", encoding="utf-8")
            (src / "bad.docx").write_text("non e uno zip", encoding="utf-8")
            llm = FakeLLMProvider(
                [
                    json.dumps(
                        [
                            {
                                "title": "Buono",
                                "retrieval_text": "x",
                                "summary": "s",
                                "supported_claims": ["x"],
                                "confidence": 0.9,
                            }
                        ]
                    )
                ]
            )

            result = ingest_dir(paths, src, StaticRouter(llm))

            self.assertEqual(1, result["files"])
            self.assertEqual(1, result["notes_written"])
            self.assertEqual(1, len(result["failed"]))
            self.assertEqual("bad.docx", result["failed"][0]["file"])

    def test_remember_session_skips_trivial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()

            result = remember_session(paths, "ok grazie", "", StaticRouter(FakeLLMProvider([])))

            self.assertTrue(result["skipped"])
            self.assertEqual(0, result["notes_written"])
            self.assertEqual([], load_notes(paths))

    def test_ingest_text_name_cannot_escape_the_raw_dir(self) -> None:
        # a prompt-injected agent via the MCP ingest_text tool passes a traversal name
        from talamus.naming import note_slug

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            note = json.dumps(
                [{"title": "X", "retrieval_text": "x", "summary": "s", "confidence": 0.9}]
            )
            ingest_text(
                paths, "text", StaticRouter(FakeLLMProvider([note])), name="../../notes/Pwned"
            )
            raw_root = paths.raw.resolve()
            for f in paths.raw.rglob("*"):
                if f.is_file():
                    self.assertEqual(f.resolve().parent, raw_root)  # never escaped the raw dir
        self.assertNotIn("/", note_slug("../../notes/Pwned"))
        self.assertNotIn("\\", note_slug("../../notes/Pwned"))


if __name__ == "__main__":
    unittest.main()
