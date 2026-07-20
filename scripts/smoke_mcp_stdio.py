"""Run an MCP initialization and tool-discovery smoke test against a command."""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "ask",
    "history",
    "ingest_text",
    "neighbors",
    "ontology_status",
    "overview",
    "propose_note",
    "read_note",
    "recall",
    "remember",
    "review_apply",
    "review_list",
    "review_reject",
    "search",
    "sources",
    "verify",
}


async def smoke(command: str, args: list[str]) -> None:
    parameters = StdioServerParameters(command=command, args=args)
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()

    actual = {tool.name for tool in result.tools}
    if actual != EXPECTED_TOOLS:
        missing = sorted(EXPECTED_TOOLS - actual)
        unexpected = sorted(actual - EXPECTED_TOOLS)
        raise RuntimeError(f"MCP tool mismatch: missing={missing}, unexpected={unexpected}")

    print(f"MCP SMOKE GREEN: initialized and discovered {len(actual)} tools")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: smoke_mcp_stdio.py COMMAND [ARG ...]")
    asyncio.run(smoke(sys.argv[1], sys.argv[2:]))


if __name__ == "__main__":
    main()
