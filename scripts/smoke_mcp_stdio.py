"""Run a read-only MCP smoke test against a command."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

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


def _result_code(value: Any) -> str | None:
    """Find a structured Talamus result code across MCP SDK 1.x/2.x shapes."""
    if isinstance(value, dict):
        code = value.get("code")
        if isinstance(code, str):
            return code
        for nested in value.values():
            found = _result_code(nested)
            if found is not None:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _result_code(nested)
            if found is not None:
                return found
    return None


def _call_result_code(result: Any) -> str | None:
    structured = getattr(result, "structuredContent", None)
    code = _result_code(structured)
    if code is not None:
        return code
    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if not isinstance(text, str):
            continue
        try:
            code = _result_code(json.loads(text))
        except json.JSONDecodeError:
            continue
        if code is not None:
            return code
    return None


async def smoke(command: str, args: list[str]) -> None:
    parameters = StdioServerParameters(command=command, args=args)
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            denial = await session.call_tool("remember", {"text": "MCP read-only smoke probe"})

    actual = {tool.name for tool in result.tools}
    if actual != EXPECTED_TOOLS:
        missing = sorted(EXPECTED_TOOLS - actual)
        unexpected = sorted(actual - EXPECTED_TOOLS)
        raise RuntimeError(f"MCP tool mismatch: missing={missing}, unexpected={unexpected}")
    denial_code = _call_result_code(denial)
    if denial_code != "mcp_writes_disabled":
        raise RuntimeError(
            "MCP default write gate failed: "
            f"expected code='mcp_writes_disabled', got {denial_code!r}; result={denial!r}"
        )

    print(
        f"MCP SMOKE GREEN: initialized, discovered {len(actual)} tools, "
        "and denied a default mutation"
    )


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: smoke_mcp_stdio.py COMMAND [ARG ...]")
    asyncio.run(smoke(sys.argv[1], sys.argv[2:]))


if __name__ == "__main__":
    main()
