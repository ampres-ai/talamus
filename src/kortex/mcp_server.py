"""Server MCP di sola lettura per il brain Kortex.

Dipende dall'extra opzionale `mcp` (`pip install kortex[mcp]`). Il resto del
pacchetto NON dipende da `mcp`: questo modulo si importa solo quando serve l'MCP.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from kortex.paths import KortexPaths
from kortex.recall import read_note_text, recall_context, search_notes

server = FastMCP("kortex")

_root: Path = Path(".").resolve()


def _paths() -> KortexPaths:
    return KortexPaths(_root)


@server.tool()
def search(query: str) -> str:
    """Cerca nel brain Kortex le schede pertinenti a una query; restituisce titoli e riassunti."""
    results = search_notes(_paths(), query)
    if not results:
        return "Nessuna scheda pertinente nel brain."
    return "\n".join(f"- {item['title']}: {item['summary']}" for item in results)


@server.tool()
def read_note(title: str) -> str:
    """Leggi il contenuto completo (Markdown) di una scheda del brain Kortex dato il titolo."""
    text = read_note_text(_paths(), title)
    return text if text is not None else f"Scheda non trovata: {title}"


@server.tool()
def recall(question: str) -> str:
    """Recupera dal brain Kortex il contesto pertinente a una domanda (schede reali). Ragiona tu sul contesto per rispondere."""
    return recall_context(_paths(), question)


def main() -> None:
    global _root
    parser = argparse.ArgumentParser(prog="kortex-mcp", description="Server MCP di lettura per il brain Kortex.")
    parser.add_argument("--root", default=".", help="Cartella del brain Kortex.")
    args = parser.parse_args()
    _root = Path(args.root).resolve()
    server.run()


if __name__ == "__main__":
    main()
