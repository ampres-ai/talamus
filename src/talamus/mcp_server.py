"""Capability-gated MCP server for a Talamus brain.

Depends on the optional `mcp` extra (`pip install talamus[mcp]`). The rest of the
package does NOT depend on `mcp`: this module is imported only when the MCP is used.
"""

from __future__ import annotations

import argparse
from importlib import import_module
from pathlib import Path
from typing import Any

from mcp.types import ToolAnnotations

from talamus.config import load_or_default
from talamus.paths import TalamusPaths
from talamus.routing import EngineRouter
from talamus.services.ask import ask_brain
from talamus.services.graph import list_graph_neighbors
from talamus.services.ingestion import ingest_raw_text
from talamus.services.library import get_library_note
from talamus.services.ontology import get_ontology_status
from talamus.services.query import (
    brain_overview,
    note_history_view,
    recall_brain,
    search_brain,
)
from talamus.services.query import read_note as read_note_service
from talamus.services.review import (
    apply_review_item,
    list_review_items,
    propose_review_note,
    reject_review_item,
)
from talamus.services.verification import verify_single_note

# MCP SDK 2.x renamed FastMCP to MCPServer and removed the old symbol. Resolve
# the class dynamically so one package can remain compatible with both maintained
# major lines without making either import path mandatory at type-check time.
_mcp_server_module = import_module("mcp.server")
_MCPServer: Any = getattr(_mcp_server_module, "MCPServer", None)
if _MCPServer is None:  # MCP SDK 1.x
    _MCPServer = _mcp_server_module.FastMCP

server = _MCPServer("talamus")

_root: Path = Path(".").resolve()
_writes_enabled = False
_central_writes_enabled = False


def _tool_annotations(
    title: str,
    *,
    read_only: bool,
    destructive: bool,
    idempotent: bool,
    open_world: bool,
) -> ToolAnnotations:
    """Describe a tool's real side effects for MCP clients and reviewers."""
    # MCP 1.x accepts the protocol's camelCase aliases at construction time,
    # while MCP 2.x type checkers expose the Python field names. Validating the
    # wire-format object preserves the same values on both maintained majors.
    return ToolAnnotations.model_validate(
        {
            "title": title,
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "idempotentHint": idempotent,
            "openWorldHint": open_world,
        }
    )


def _paths() -> TalamusPaths:
    return TalamusPaths(_root)


def _mutation_result(
    ok: bool,
    code: str,
    message: str,
    *,
    required_flags: tuple[str, ...] = (),
    **data: object,
) -> dict[str, object]:
    """Return a stable, structured result for every MCP mutation."""
    result: dict[str, object] = {"ok": ok, "code": code, "message": message}
    if required_flags:
        result["required_flags"] = list(required_flags)
    result.update(data)
    return result


def _set_write_capabilities(*, writes: bool, central_writes: bool) -> None:
    if central_writes and not writes:
        raise ValueError("--enable-central-writes requires --enable-writes")
    global _writes_enabled, _central_writes_enabled
    _writes_enabled = writes
    _central_writes_enabled = central_writes


def _project_write_denial(tool: str) -> dict[str, object] | None:
    if _writes_enabled:
        return None
    return _mutation_result(
        False,
        "mcp_writes_disabled",
        (
            f"{tool} is disabled because this MCP server is read-only; "
            "restart it with --enable-writes."
        ),
        required_flags=("--enable-writes",),
    )


def _write_root(scope: str, tool: str) -> tuple[Path | None, dict[str, object] | None]:
    if scope not in {"project", "central"}:
        return None, _mutation_result(
            False,
            "mcp_scope_invalid",
            "scope must be exactly 'project' or 'central'.",
            allowed_scopes=["project", "central"],
        )
    denied = _project_write_denial(tool)
    if denied is not None:
        return None, denied
    if scope == "project":
        return _root, None
    if not _central_writes_enabled:
        return None, _mutation_result(
            False,
            "mcp_central_writes_disabled",
            f"{tool} cannot write to the central brain without the stronger explicit opt-in.",
            required_flags=("--enable-writes", "--enable-central-writes"),
        )
    from talamus.registry import central_brain

    central = central_brain()
    if central is None:
        return None, _mutation_result(
            False,
            "mcp_central_brain_missing",
            (
                "No central brain is registered; initialize or register one "
                "before requesting a central write."
            ),
        )
    return Path(central.root()), None


def _router() -> EngineRouter:
    return EngineRouter(load_or_default(_paths().config_path))


@server.tool(
    annotations=_tool_annotations(
        "Search brain",
        read_only=False,
        destructive=False,
        idempotent=False,
        open_world=True,
    )
)
def search(query: str, smart: bool = False) -> str:
    """Search the Talamus brain for notes relevant to a query; returns titles and summaries.

    With smart=True the query is expanded by the LLM before searching (Query2doc,
    cached): it breaks the lexical ceiling on vague questions, at the cost of one LLM
    call per new query."""
    query_text = query
    if smart:
        from talamus.smartsearch import expand_query

        query_text = expand_query(
            _paths(),
            query,
            _router(),
            persist_cache=_writes_enabled,
        )
    result = search_brain(_root, query_text)
    if not result.success or result.data is None:
        return result.message
    if not result.data.hits:
        return "No relevant note in the brain."
    return "\n".join(f"- {hit.title}: {hit.summary}" for hit in result.data.hits)


@server.tool(
    annotations=_tool_annotations(
        "Read note",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
    )
)
def read_note(title: str, as_of: str = "") -> str:
    """Read the full Markdown content of a Talamus note given its title.

    Optional as_of (a date like "2026-01" or "2026-01-15"): read the note AS IT
    WAS at that moment — Talamus keeps every note's history, so you can check
    what was believed at a past date before trusting or updating it."""
    result = read_note_service(_root, title, as_of=as_of or None)
    data = result.data
    if data is None:
        return f"Note not found: {title}"
    if as_of:
        if not result.success or data.version is None:
            return result.message
        version = data.version
        body = "\n".join(str(v) for v in version.get("body_sections", {}).values())
        return f"[as of {as_of}] {title}\n{version.get('summary', '')}\n\n{body}".strip()
    if data.markdown is not None:
        return data.markdown
    return f"Note not found: {title}"


@server.tool(
    annotations=_tool_annotations(
        "Ask brain",
        read_only=True,
        destructive=False,
        idempotent=False,
        open_world=True,
    )
)
def ask(question: str) -> str:
    """Ask the brain and get a written answer WITH CITATIONS to the exact notes
    used. Spends LLM calls on the user's configured engine (cheap tier for the
    routing, strong tier for the answer). Prefer `recall` when you only need raw
    context to reason over yourself — it costs zero LLM calls."""
    result = ask_brain(_root, question, router=_router())
    if result.data is None:
        return result.message
    data = result.data
    if not data.answered:
        listing = "\n".join(f"- {s.title}: {s.summary}" for s in data.sources)
        return f"{data.notice}\n{listing}".strip()
    return data.answer


@server.tool(
    annotations=_tool_annotations(
        "Verify note",
        read_only=True,
        destructive=False,
        idempotent=False,
        open_world=True,
    )
)
def verify(title: str) -> str:
    """Check whether a note is still faithful to its ORIGINAL source (Talamus
    preserves the source of every note). Returns ok, a proposed correction, or
    unchecked when the source is unavailable. Costs one LLM call when the source
    exists — use it before relying on a note that smells stale."""
    result = verify_single_note(_root, title, _router())
    if not result.success or result.data is None:
        return result.message
    data = result.data
    if not data.found:
        return f"Note not found: {title}"
    if not data.checked:
        return f"{title}: source unavailable — verification skipped (provenance may be stale)."
    if data.ok:
        return f"{title}: OK — still faithful to its source."
    correction = data.summary or data.body or "see the review queue"
    return f"{title}: MISMATCH with its source — proposed correction: {correction}"


@server.tool(
    annotations=_tool_annotations(
        "Recall context",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
    )
)
def recall(question: str) -> str:
    """Recall from the Talamus brain the context relevant to a question (real notes).
    Reason over the context yourself to answer."""
    result = recall_brain(_root, question)
    return result.data.context if result.success and result.data is not None else result.message


@server.tool(
    annotations=_tool_annotations(
        "Brain overview",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
    )
)
def overview() -> str:
    """Show the Talamus brain's domain map (name, description, note count): an
    overview to get oriented before searching. Read-only, no LLM cost."""
    result = brain_overview(_root)
    if not result.success or result.data is None:
        return result.message
    domains = result.data.domains
    if not domains:
        return "No domain map yet. Run `talamus overview` to build it."
    lines: list[str] = []
    for domain in domains:
        members = domain.get("members", [])
        lines.append(f"## {domain.get('name', '?')}  ({len(members)} notes)")
        if domain.get("description"):
            lines.append(f"   {domain['description']}")
    return "\n".join(lines)


@server.tool(
    annotations=_tool_annotations(
        "Concept neighbors",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
    )
)
def neighbors(concept: str, include_inferred: bool = True) -> str:
    """Show concepts connected to a concept in the brain, with relation types.

    include_inferred=False hides derived ontology-inference edges.
    """
    result = list_graph_neighbors(_root, concept, include_inferred=include_inferred)
    if not result.success or result.data is None:
        return result.message
    if not result.data:
        return "No connected concept."
    lines: list[str] = []
    for item in result.data:
        arrow = "->" if item.direction == "out" else "<-"
        suffix = ""
        if item.inferred:
            suffix = f" (inferred: {item.rule} via {'; '.join(item.via)})"
        lines.append(f"{arrow} [{item.relation}] {item.title}{suffix}")
    return "\n".join(lines)


@server.tool(
    annotations=_tool_annotations(
        "Note history",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
    )
)
def history(title: str) -> str:
    """The past versions of a brain note (transaction time), oldest first: when
    Talamus changed that record and how."""
    result = note_history_view(_root, title)
    if not result.success or result.data is None:
        return result.message
    versions = result.data.versions
    if not versions:
        return f"No version for: {title}"
    return "\n".join(f"[{v.get('updated_at', '?')}] {v.get('summary', '')}" for v in versions)


@server.tool(
    annotations=_tool_annotations(
        "Note sources",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
    )
)
def sources(title: str) -> str:
    """The sources (provenance) of a note: where each statement comes from."""
    result = get_library_note(_root, title)
    if not result.success or result.data is None or not result.data.found:
        return f"Note not found: {title}"
    note_sources = result.data.sources
    if not note_sources:
        return "The note has no recorded sources."
    return "\n".join(f"- {s['normalized_path']} ({s['locator']})" for s in note_sources)


@server.tool(
    annotations=_tool_annotations(
        "Ontology status",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
    )
)
def ontology_status() -> str:
    """The state of the emergent type system: schema version, active/candidate types,
    and the coverage of typed edges."""
    result = get_ontology_status(_root)
    if not result.success or result.data is None:
        return result.message
    report = result.data
    cov = report.coverage
    lines = [f"schema {report.schema_id} (v{report.version})"]
    for state, count in sorted(report.types.items()):
        lines.append(f"{state}: {count}")
    if cov.get("edges"):
        lines.append(f"coverage: {cov.get('non_related')}/{cov.get('edges')} typed edges")
    return "\n".join(lines)


@server.tool(
    annotations=_tool_annotations(
        "Remember insight",
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=True,
    )
)
def remember(text: str, scope: str = "project") -> dict[str, object]:
    """Save into the Talamus brain an important insight or decision that emerged in
    the session, turning it into a note. scope: 'project' (default) or 'central' for
    the personal brain. Requires --enable-writes; central additionally requires
    --enable-central-writes."""
    target, denied = _write_root(scope, "remember")
    if denied is not None or target is None:
        return denied or _mutation_result(
            False, "mcp_write_target_missing", "Write target missing."
        )
    result = ingest_raw_text(target, text, _router())
    if not result.success or result.data is None:
        return _mutation_result(False, result.code or "mcp_remember_failed", result.message)
    return _mutation_result(
        True,
        "mcp_remembered",
        f"Remembered in [{scope}]: {result.data.notes_written} notes saved.",
        scope=scope,
        notes_written=result.data.notes_written,
    )


@server.tool(
    annotations=_tool_annotations(
        "Ingest text",
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=True,
    )
)
def ingest_text(text: str, name: str = "insight", scope: str = "project") -> dict[str, object]:
    """Compile a text into brain notes (without the 'worth remembering' gate: use it
    for already-selected content). scope: 'project' (default) or 'central'. Requires
    --enable-writes; central additionally requires --enable-central-writes."""
    target, denied = _write_root(scope, "ingest_text")
    if denied is not None or target is None:
        return denied or _mutation_result(
            False, "mcp_write_target_missing", "Write target missing."
        )
    result = ingest_raw_text(target, text, _router(), name=name)
    if not result.success or result.data is None:
        return _mutation_result(False, result.code or "mcp_ingest_failed", result.message)
    return _mutation_result(
        True,
        "mcp_text_ingested",
        f"Ingested in [{scope}]: {result.data.notes_written} notes.",
        scope=scope,
        notes_written=result.data.notes_written,
    )


@server.tool(
    annotations=_tool_annotations(
        "Propose note",
        read_only=False,
        destructive=False,
        idempotent=False,
        open_world=False,
    )
)
def propose_note(text: str, reason: str = "") -> dict[str, object]:
    """Propose UNCERTAIN knowledge: it lands in the brain's review queue, not directly
    in the notes (F10.4). A human will apply or reject it. Requires --enable-writes."""
    denied = _project_write_denial("propose_note")
    if denied is not None:
        return denied
    result = propose_review_note(_root, text, reason)
    if not result.success or result.data is None:
        return _mutation_result(False, result.code or "mcp_proposal_failed", result.message)
    return _mutation_result(
        True,
        "mcp_note_proposed",
        f"In review: {result.data.item_id} (decide with `talamus review`).",
        item_id=result.data.item_id,
    )


@server.tool(
    annotations=_tool_annotations(
        "List review queue",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
    )
)
def review_list() -> str:
    """The decisions pending in the brain's review queue."""
    result = list_review_items(_root, status="pending")
    if not result.success or result.data is None:
        return result.message
    if not result.data:
        return "Review queue empty."
    return "\n".join(f"- {i.item_id} [{i.kind}] {i.title}" for i in result.data)


@server.tool(
    annotations=_tool_annotations(
        "Apply review item",
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=False,
    )
)
def review_apply(item_id: str) -> dict[str, object]:
    """Apply an item from the review queue (corrections are written to the brain while
    preserving history). Requires --enable-writes."""
    denied = _project_write_denial("review_apply")
    if denied is not None:
        return denied
    result = apply_review_item(_root, item_id)
    return _mutation_result(
        result.success,
        "mcp_review_applied" if result.success else (result.code or "mcp_review_apply_failed"),
        f"Applied: {item_id}" if result.success else result.message,
        item_id=item_id,
    )


@server.tool(
    annotations=_tool_annotations(
        "Reject review item",
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=False,
    )
)
def review_reject(item_id: str, reason: str = "") -> dict[str, object]:
    """Reject an item from the review queue (the decision stays recorded).
    Requires --enable-writes."""
    denied = _project_write_denial("review_reject")
    if denied is not None:
        return denied
    result = reject_review_item(_root, item_id, reason)
    return _mutation_result(
        result.success,
        "mcp_review_rejected" if result.success else (result.code or "mcp_review_reject_failed"),
        f"Rejected: {item_id}" if result.success else result.message,
        item_id=item_id,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="talamus-mcp",
        description="Read-only MCP server for a Talamus brain; writes require explicit flags.",
    )
    parser.add_argument("--root", default=".", help="The Talamus brain folder.")
    capability = parser.add_mutually_exclusive_group()
    capability.add_argument(
        "--read-only",
        action="store_true",
        help="Expose the default read-only capability (explicit form used by generated configs).",
    )
    capability.add_argument(
        "--enable-writes",
        action="store_true",
        help="Allow project-brain mutations from MCP tools.",
    )
    parser.add_argument(
        "--enable-central-writes",
        action="store_true",
        help="Also allow central-brain mutations; requires --enable-writes.",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve over local HTTP instead of stdio (for desktop clients that need it).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for --http (default: local).")
    parser.add_argument("--port", type=int, default=8000, help="Port for --http.")
    return parser


def _run_http(host: str, port: int) -> None:
    """Run HTTP on MCP SDK 1.x or 2.x without changing the public CLI."""
    settings = server.settings
    if hasattr(settings, "host"):
        # MCP 1.x stores transport configuration on the server settings object.
        settings.host = host
        settings.port = port
        server.run(transport="streamable-http")
        return

    # MCP 2.x moved transport configuration to ``run``.
    server.run(transport="streamable-http", host=host, port=port)


def main(argv: list[str] | None = None) -> None:
    global _root
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.enable_central_writes and not args.enable_writes:
        parser.error("--enable-central-writes requires --enable-writes")
    _root = Path(args.root).resolve()
    _set_write_capabilities(
        writes=args.enable_writes,
        central_writes=args.enable_central_writes,
    )
    if args.http:
        _run_http(args.host, args.port)
    else:
        server.run()


if __name__ == "__main__":
    main()
