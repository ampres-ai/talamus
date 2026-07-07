"""Read+write MCP server for a Talamus brain.

Depends on the optional `mcp` extra (`pip install talamus[mcp]`). The rest of the
package does NOT depend on `mcp`: this module is imported only when the MCP is used.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

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

server = FastMCP("talamus")

_root: Path = Path(".").resolve()


def _paths() -> TalamusPaths:
    return TalamusPaths(_root)


def _root_for(scope: str) -> Path:
    """Resolve the brain root for an explicit scope (F10.1): 'project' (default) or
    'central' (the personal hub). Writes default to the project brain (F10.4)."""
    if scope == "central":
        from talamus.registry import central_brain

        central = central_brain()
        if central is not None:
            return Path(central.root())
    return _root


def _router() -> EngineRouter:
    return EngineRouter(load_or_default(_paths().config_path))


@server.tool()
def search(query: str, smart: bool = False) -> str:
    """Search the Talamus brain for notes relevant to a query; returns titles and summaries.

    With smart=True the query is expanded by the LLM before searching (Query2doc,
    cached): it breaks the lexical ceiling on vague questions, at the cost of one LLM
    call per new query."""
    query_text = query
    if smart:
        from talamus.smartsearch import expand_query

        query_text = expand_query(_paths(), query, _router())
    result = search_brain(_root, query_text)
    if not result.success or result.data is None:
        return result.message
    if not result.data.hits:
        return "No relevant note in the brain."
    return "\n".join(f"- {hit.title}: {hit.summary}" for hit in result.data.hits)


@server.tool()
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


@server.tool()
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


@server.tool()
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


@server.tool()
def recall(question: str) -> str:
    """Recall from the Talamus brain the context relevant to a question (real notes).
    Reason over the context yourself to answer."""
    result = recall_brain(_root, question)
    return result.data.context if result.success and result.data is not None else result.message


@server.tool()
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


@server.tool()
def neighbors(concept: str) -> str:
    """Show the concepts connected to a concept in the brain (the map/ontology),
    with the relation type."""
    result = list_graph_neighbors(_root, concept)
    if not result.success or result.data is None:
        return result.message
    if not result.data:
        return "No connected concept."
    return "\n".join(
        f"{'->' if item.direction == 'out' else '<-'} [{item.relation}] {item.title}"
        for item in result.data
    )


@server.tool()
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


@server.tool()
def sources(title: str) -> str:
    """The sources (provenance) of a note: where each statement comes from."""
    result = get_library_note(_root, title)
    if not result.success or result.data is None or not result.data.found:
        return f"Note not found: {title}"
    note_sources = result.data.sources
    if not note_sources:
        return "The note has no recorded sources."
    return "\n".join(f"- {s['normalized_path']} ({s['locator']})" for s in note_sources)


@server.tool()
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


@server.tool()
def remember(text: str, scope: str = "project") -> str:
    """Save into the Talamus brain an important insight or decision that emerged in
    the session, turning it into a note. scope: 'project' (default) or 'central' for
    the personal brain — writing to the global brain must be explicit."""
    result = ingest_raw_text(_root_for(scope), text, _router())
    if not result.success or result.data is None:
        return result.message
    return f"Remembered in [{scope}]: {result.data.notes_written} notes saved."


@server.tool()
def ingest_text(text: str, name: str = "insight", scope: str = "project") -> str:
    """Compile a text into brain notes (without the 'worth remembering' gate: use it
    for already-selected content). scope: 'project' (default) or 'central'."""
    result = ingest_raw_text(_root_for(scope), text, _router(), name=name)
    if not result.success or result.data is None:
        return result.message
    return f"Ingested in [{scope}]: {result.data.notes_written} notes."


@server.tool()
def propose_note(text: str, reason: str = "") -> str:
    """Propose UNCERTAIN knowledge: it lands in the brain's review queue, not directly
    in the notes (F10.4). A human will apply or reject it."""
    result = propose_review_note(_root, text, reason)
    if not result.success or result.data is None:
        return result.message
    return f"In review: {result.data.item_id} (decide with `talamus review`)."


@server.tool()
def review_list() -> str:
    """The decisions pending in the brain's review queue."""
    result = list_review_items(_root, status="pending")
    if not result.success or result.data is None:
        return result.message
    if not result.data:
        return "Review queue empty."
    return "\n".join(f"- {i.item_id} [{i.kind}] {i.title}" for i in result.data)


@server.tool()
def review_apply(item_id: str) -> str:
    """Apply an item from the review queue (corrections are written to the brain while
    preserving history)."""
    result = apply_review_item(_root, item_id)
    return f"Applied: {item_id}" if result.success else result.message


@server.tool()
def review_reject(item_id: str, reason: str = "") -> str:
    """Reject an item from the review queue (the decision stays recorded)."""
    result = reject_review_item(_root, item_id, reason)
    return f"Rejected: {item_id}" if result.success else result.message


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="talamus-mcp", description="Read/write MCP server for a Talamus brain."
    )
    parser.add_argument("--root", default=".", help="The Talamus brain folder.")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve over local HTTP instead of stdio (for desktop clients that need it).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for --http (default: local).")
    parser.add_argument("--port", type=int, default=8000, help="Port for --http.")
    return parser


def main(argv: list[str] | None = None) -> None:
    global _root
    args = _build_parser().parse_args(argv)
    _root = Path(args.root).resolve()
    if args.http:
        server.settings.host = args.host
        server.settings.port = args.port
        server.run(transport="streamable-http")
    else:
        server.run()


if __name__ == "__main__":
    main()
