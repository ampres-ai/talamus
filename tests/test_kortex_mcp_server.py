import asyncio
import unittest

try:
    import mcp  # noqa: F401

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@unittest.skipUnless(HAS_MCP, "mcp non installato (extra opzionale kortex[mcp])")
class McpServerTests(unittest.TestCase):
    def test_module_builds_a_fastmcp_server(self) -> None:
        from mcp.server.fastmcp import FastMCP

        from kortex import mcp_server

        self.assertIsInstance(mcp_server.server, FastMCP)

    def test_registers_the_three_read_tools(self) -> None:
        from kortex import mcp_server

        tools = asyncio.run(mcp_server.server.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual({"search", "read_note", "recall"}, names)

    def test_http_flag_is_parsed(self) -> None:
        from kortex import mcp_server

        args = mcp_server._build_parser().parse_args(
            ["--http", "--host", "127.0.0.1", "--port", "9000", "--root", "x"]
        )
        self.assertTrue(args.http)
        self.assertEqual(9000, args.port)
        self.assertEqual("x", args.root)


if __name__ == "__main__":
    unittest.main()
