"""Server MCP di sola lettura per il brain Talamus.

Dipende dall'extra opzionale `mcp` (`pip install talamus[mcp]`). Il resto del
pacchetto NON dipende da `mcp`: questo modulo si importa solo quando serve l'MCP.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from talamus.adapters.llm import ClaudeCliProvider
from talamus.ingest import ingest_text
from talamus.paths import TalamusPaths
from talamus.recall import concept_neighbors, read_note_text, recall_context, search_notes

server = FastMCP("talamus")

_llm = ClaudeCliProvider()

_root: Path = Path(".").resolve()


def _paths() -> TalamusPaths:
    return TalamusPaths(_root)


@server.tool()
def search(query: str) -> str:
    """Cerca nel brain Talamus le schede pertinenti a una query; restituisce titoli e riassunti."""
    results = search_notes(_paths(), query)
    if not results:
        return "Nessuna scheda pertinente nel brain."
    return "\n".join(f"- {item['title']}: {item['summary']}" for item in results)


@server.tool()
def read_note(title: str) -> str:
    """Leggi il contenuto completo (Markdown) di una scheda del brain Talamus dato il titolo."""
    text = read_note_text(_paths(), title)
    return text if text is not None else f"Scheda non trovata: {title}"


@server.tool()
def recall(question: str) -> str:
    """Recupera dal brain Talamus il contesto pertinente a una domanda (schede reali).
    Ragiona tu sul contesto per rispondere."""
    return recall_context(_paths(), question)


@server.tool()
def neighbors(concept: str) -> str:
    """Mostra i concetti collegati a un concetto nel brain (la mappa/ontologia),
    con il tipo di relazione."""
    items = concept_neighbors(_paths(), concept)
    if not items:
        return "Nessun concetto collegato."
    return "\n".join(
        f"{'->' if item['direction'] == 'out' else '<-'} [{item['relation']}] {item['title']}"
        for item in items
    )


@server.tool()
def remember(text: str) -> str:
    """Salva nel brain Talamus un'intuizione o decisione importante emersa nella
    sessione, trasformandola in una scheda."""
    result = ingest_text(_paths(), text, _llm)
    return f"Ricordato: {result['notes_written']} schede salvate nel brain."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="talamus-mcp", description="Server MCP di lettura per il brain Talamus."
    )
    parser.add_argument("--root", default=".", help="Cartella del brain Talamus.")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Servi su HTTP locale invece di stdio (per client desktop che lo richiedono).",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host per --http (predefinito: locale)."
    )
    parser.add_argument("--port", type=int, default=8000, help="Porta per --http.")
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
