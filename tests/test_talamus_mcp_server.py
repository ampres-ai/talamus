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
    def test_module_builds_an_mcp_server(self) -> None:
        try:
            from mcp.server import MCPServer as ServerClass
        except ImportError:
            from mcp.server import FastMCP as ServerClass

        from talamus import mcp_server

        self.assertIsInstance(mcp_server.server, ServerClass)

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
            # moats as agent tools (P6: the agent is a first-class curator)
            "ask",
            "verify",
            # write (F10.3)
            "remember",
            "ingest_text",
            "propose_note",
            "review_list",
            "review_apply",
            "review_reject",
        }
        self.assertEqual(expected, names)
        expected_annotations = {
            "search": (False, False, False, True),
            "read_note": (True, False, True, False),
            "ask": (True, False, False, True),
            "verify": (True, False, False, True),
            "recall": (True, False, True, False),
            "overview": (True, False, True, False),
            "neighbors": (True, False, True, False),
            "history": (True, False, True, False),
            "sources": (True, False, True, False),
            "ontology_status": (True, False, True, False),
            "remember": (False, True, False, True),
            "ingest_text": (False, True, False, True),
            "propose_note": (False, False, False, False),
            "review_list": (True, False, True, False),
            "review_apply": (False, True, False, False),
            "review_reject": (False, True, False, False),
        }
        for tool in tools:
            self.assertTrue(tool.description, f"{tool.name} has no description")
            self.assertIsNotNone(tool.annotations, f"{tool.name} has no annotations")
            annotations = tool.annotations
            assert annotations is not None
            annotation_data = annotations.model_dump(by_alias=True)
            self.assertTrue(annotation_data["title"], f"{tool.name} has no display title")
            self.assertEqual(
                expected_annotations[tool.name],
                (
                    annotation_data["readOnlyHint"],
                    annotation_data["destructiveHint"],
                    annotation_data["idempotentHint"],
                    annotation_data["openWorldHint"],
                ),
                f"{tool.name} annotations do not match its behavior",
            )

    def test_http_flag_is_parsed(self) -> None:
        from talamus import mcp_server

        args = mcp_server._build_parser().parse_args(
            ["--http", "--host", "127.0.0.1", "--port", "9000", "--root", "x"]
        )
        self.assertTrue(args.http)
        self.assertEqual(9000, args.port)
        self.assertEqual("x", args.root)

    def test_http_transport_supports_both_mcp_sdk_configuration_models(self) -> None:
        from talamus import mcp_server

        class _V1Settings:
            host = "127.0.0.1"
            port = 8000

        class _V1Server:
            settings = _V1Settings()
            calls: list[dict[str, object]] = []

            def run(self, **kwargs: object) -> None:
                self.calls.append(kwargs)

        class _V2Settings:
            pass

        class _V2Server:
            settings = _V2Settings()
            calls: list[dict[str, object]] = []

            def run(self, **kwargs: object) -> None:
                self.calls.append(kwargs)

        original = mcp_server.server
        try:
            v1 = _V1Server()
            mcp_server.server = v1
            mcp_server._run_http("0.0.0.0", 9101)
            self.assertEqual("0.0.0.0", v1.settings.host)
            self.assertEqual(9101, v1.settings.port)
            self.assertEqual([{"transport": "streamable-http"}], v1.calls)

            v2 = _V2Server()
            mcp_server.server = v2
            mcp_server._run_http("0.0.0.0", 9102)
            self.assertEqual(
                [{"transport": "streamable-http", "host": "0.0.0.0", "port": 9102}],
                v2.calls,
            )
        finally:
            mcp_server.server = original


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

    def test_read_note_as_of_reads_the_past_not_the_present(self) -> None:
        """The temporal moat as an agent tool: as_of answers 'what was believed
        at that date' — a date before the note existed yields no version."""
        from talamus import mcp_server

        with tempfile.TemporaryDirectory() as tmp:
            self._brain(tmp)
            mcp_server._root = Path(tmp)
            try:
                today = mcp_server.read_note("Reranking")
                self.assertIn("Reranking", today)
                past = mcp_server.read_note("Reranking", as_of="2020-01-01")
                self.assertIn("No version", past)
            finally:
                mcp_server._root = Path(".").resolve()

    def test_verify_reports_without_crashing_and_without_engine_when_unchecked(self) -> None:
        """The verifiability moat as an agent tool."""
        import json
        from unittest.mock import patch

        from talamus import mcp_server
        from talamus.routing import StaticRouter
        from tests.support import FakeLLMProvider

        with tempfile.TemporaryDirectory() as tmp:
            self._brain(tmp)
            mcp_server._root = Path(tmp)
            try:
                fake = StaticRouter(FakeLLMProvider([json.dumps({"ok": True})]))
                with patch("talamus.mcp_server._router", return_value=fake):
                    out = mcp_server.verify("Reranking")
                self.assertIsInstance(out, str)
                self.assertIn("Reranking", out)
                missing = mcp_server.verify("Nota Inesistente")
                self.assertIn("not found", missing.lower())
            finally:
                mcp_server._root = Path(".").resolve()

    def test_ask_returns_a_cited_answer_through_the_router(self) -> None:
        from unittest.mock import patch

        from talamus import mcp_server
        from talamus.routing import StaticRouter

        class _Fake:
            label = "Fake Engine"

            def complete(self, prompt: str) -> str:
                return "QQZ synthesized answer citing [1]."

        with tempfile.TemporaryDirectory() as tmp:
            self._brain(tmp)
            mcp_server._root = Path(tmp)
            try:
                with patch("talamus.mcp_server._router", return_value=StaticRouter(_Fake())):
                    out = mcp_server.ask("what is retrieval augmented generation?")
                self.assertIn("QQZ", out)
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
