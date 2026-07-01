import asyncio
import tempfile
import unittest
from pathlib import Path

try:
    import mcp  # noqa: F401

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@unittest.skipUnless(HAS_MCP, "mcp not installed (optional extra talamus[mcp])")
class McpServerTests(unittest.TestCase):
    def test_module_builds_a_fastmcp_server(self) -> None:
        from mcp.server.fastmcp import FastMCP

        from talamus import mcp_server

        self.assertIsInstance(mcp_server.server, FastMCP)

    def test_registers_the_full_tool_set(self) -> None:
        """F10.2/F10.3: every read and write tool has a schema."""
        from talamus import mcp_server

        tools = asyncio.run(mcp_server.server.list_tools())
        names = {tool.name for tool in tools}
        expected = {
            # read (F10.2)
            "search",
            "read_note",
            "recall",
            "overview",
            "neighbors",
            "history",
            "sources",
            "ontology_status",
            # write (F10.3)
            "remember",
            "ingest_text",
            "propose_note",
            "review_list",
            "review_apply",
            "review_reject",
        }
        self.assertEqual(expected, names)
        for tool in tools:
            self.assertTrue(tool.description, f"{tool.name} has no description")

    def test_http_flag_is_parsed(self) -> None:
        from talamus import mcp_server

        args = mcp_server._build_parser().parse_args(
            ["--http", "--host", "127.0.0.1", "--port", "9000", "--root", "x"]
        )
        self.assertTrue(args.http)
        self.assertEqual(9000, args.port)
        self.assertEqual("x", args.root)


@unittest.skipUnless(HAS_MCP, "mcp not installed (optional extra talamus[mcp])")
class McpToolBehaviorTests(unittest.TestCase):
    def _brain(self, tmp: str):
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        paths = TalamusPaths(Path(tmp))
        create_demo_brain(paths)
        return paths

    def test_propose_note_goes_to_review_not_notes(self) -> None:
        """F10.4: uncertain memories land in review, never directly in notes."""
        from talamus import mcp_server
        from talamus.review import ReviewQueue
        from talamus.store import load_notes

        with tempfile.TemporaryDirectory() as tmp:
            paths = self._brain(tmp)
            mcp_server._root = Path(tmp)
            try:
                before = len(load_notes(paths))
                message = mcp_server.propose_note("Forse X implica Y", "bassa confidenza")
                self.assertIn("review", message.lower())
                self.assertEqual(len(load_notes(paths)), before)  # notes untouched
                pending = ReviewQueue(paths).list(status="pending")
                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0].kind, "low_confidence_note")
            finally:
                mcp_server._root = Path(".").resolve()

    def test_history_and_sources_read_real_data(self) -> None:
        from talamus import mcp_server

        with tempfile.TemporaryDirectory() as tmp:
            self._brain(tmp)
            mcp_server._root = Path(tmp)
            try:
                self.assertIn("[", mcp_server.history("Reranking"))
                self.assertIn("demo", mcp_server.sources("Reranking"))
                self.assertIn("schema", mcp_server.ontology_status())
            finally:
                mcp_server._root = Path(".").resolve()


class CaptureLogTests(unittest.TestCase):
    def test_remember_session_logs_skip_and_capture_decisions(self) -> None:
        """F10.5: every capture/skip decision is auditable with its reason."""
        import json

        from talamus.ingest import remember_session
        from talamus.paths import TalamusPaths
        from talamus.routing import StaticRouter
        from tests.support import FakeLLMProvider

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            result = remember_session(paths, "ok grazie", "", StaticRouter(FakeLLMProvider([])))
            self.assertTrue(result["skipped"])
            self.assertIn("gate", result["reason"])
            log = (paths.logs / "capture.log").read_text(encoding="utf-8")
            self.assertIn("skip", log)
            transcript = (
                '{"role":"user","content":"come faccio X"}\n'
                '{"role":"assistant","content":"Si fa cosi perche serve Y"}'
            )
            note = json.dumps(
                [
                    {
                        "title": "Come fare X",
                        "retrieval_text": "x",
                        "summary": "s",
                        "supported_claims": ["x"],
                        "confidence": 0.9,
                    }
                ]
            )
            remember_session(
                paths, transcript, "diff --git a/x b/x\n+1", StaticRouter(FakeLLMProvider([note]))
            )
            log = (paths.logs / "capture.log").read_text(encoding="utf-8")
            self.assertIn("capture", log)


if __name__ == "__main__":
    unittest.main()
