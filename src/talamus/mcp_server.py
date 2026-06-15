"""Server MCP di sola lettura per il brain Talamus.

Dipende dall'extra opzionale `mcp` (`pip install talamus[mcp]`). Il resto del
pacchetto NON dipende da `mcp`: questo modulo si importa solo quando serve l'MCP.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from talamus.adapters.llm import LLMProvider, build_provider
from talamus.config import load_or_default
from talamus.domains import load_overview
from talamus.ingest import ingest_text as sdk_ingest_text
from talamus.paths import TalamusPaths
from talamus.recall import concept_neighbors, read_note_text, recall_context, search_notes

server = FastMCP("talamus")

_root: Path = Path(".").resolve()


def _paths() -> TalamusPaths:
    return TalamusPaths(_root)


def _paths_for(scope: str) -> TalamusPaths:
    """Resolve the brain for an explicit scope (F10.1): 'project' (default) or
    'central' (the personal hub). Writes default to the project brain (F10.4)."""
    if scope == "central":
        from talamus.registry import central_brain

        central = central_brain()
        if central is not None:
            return TalamusPaths(central.root())
    return _paths()


def _provider() -> LLMProvider:
    config = load_or_default(_paths().config_path)
    return build_provider(config.llm_provider, config.llm_model)


@server.tool()
def search(query: str, smart: bool = False) -> str:
    """Cerca nel brain Talamus le schede pertinenti a una query; restituisce titoli e riassunti.

    Con smart=True la query viene espansa dall'LLM prima della ricerca (Query2doc,
    cacheato): rompe il soffitto lessicale sulle domande vaghe, al costo di una
    chiamata LLM per query nuova."""
    query_text = query
    if smart:
        from talamus.smartsearch import expand_query

        query_text = expand_query(_paths(), query, _provider())
    results = search_notes(_paths(), query_text)
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
def overview() -> str:
    """Mostra la mappa dei domini del brain Talamus (nome, descrizione, numero di schede):
    una panoramica per orientarsi prima di cercare. Sola lettura, nessun costo LLM."""
    domains = load_overview(_paths())
    if not domains:
        return "Nessuna mappa dei domini. Esegui `talamus overview` per generarla."
    lines: list[str] = []
    for domain in domains:
        members = domain.get("members", [])
        lines.append(f"## {domain.get('name', '?')}  ({len(members)} schede)")
        if domain.get("description"):
            lines.append(f"   {domain['description']}")
    return "\n".join(lines)


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
def history(title: str) -> str:
    """Le versioni passate di una scheda del brain (transaction time), dalla più
    vecchia: quando Talamus ha cambiato quel record e come."""
    from talamus.timeline import note_history

    versions = note_history(_paths(), title)
    if not versions:
        return f"Nessuna versione per: {title}"
    return "\n".join(f"[{v.get('updated_at', '?')}] {v.get('summary', '')}" for v in versions)


@server.tool()
def sources(title: str) -> str:
    """Le fonti (provenienza) di una scheda: da dove viene ogni affermazione."""
    from talamus.store import load_notes

    for note in load_notes(_paths()):
        if note.title.lower() == title.strip().lower():
            if not note.sources:
                return "La scheda non ha fonti registrate."
            return "\n".join(f"- {s.normalized_path} ({s.locator})" for s in note.sources)
    return f"Scheda non trovata: {title}"


@server.tool()
def ontology_status() -> str:
    """Lo stato del sistema di tipi emergente: versione dello schema, tipi
    attivi/candidati e copertura degli archi tipizzati."""
    from talamus.ontology_lab import schema_status

    status = schema_status(_paths())
    cov = status["coverage"]
    lines = [f"schema {status['schema_id']} (v{status['version']})"]
    for state, count in sorted(status["types"].items()):
        lines.append(f"{state}: {count}")
    if cov["edges"]:
        lines.append(f"coverage: {cov['non_related']}/{cov['edges']} archi tipizzati")
    return "\n".join(lines)


@server.tool()
def remember(text: str, scope: str = "project") -> str:
    """Salva nel brain Talamus un'intuizione o decisione importante emersa nella
    sessione, trasformandola in una scheda. scope: 'project' (default) o 'central'
    per il brain personale — la scrittura globale deve essere esplicita."""
    result = sdk_ingest_text(_paths_for(scope), text, _provider())
    return f"Ricordato in [{scope}]: {result['notes_written']} schede salvate."


@server.tool()
def ingest_text(text: str, name: str = "insight", scope: str = "project") -> str:
    """Compila un testo in schede del brain (senza il gate 'vale la pena ricordare':
    usalo per contenuto già selezionato). scope: 'project' (default) o 'central'."""
    result = sdk_ingest_text(_paths_for(scope), text, _provider(), name=name)
    return f"Ingerito in [{scope}]: {result['notes_written']} schede."


@server.tool()
def propose_note(text: str, reason: str = "") -> str:
    """Proponi una conoscenza INCERTA: finisce nella coda di review del brain,
    non direttamente nelle schede (F10.4). Un umano la applicherà o rifiuterà."""
    from talamus.review import ReviewQueue

    item = ReviewQueue(_paths()).add(
        "low_confidence_note",
        text[:80] + ("…" if len(text) > 80 else ""),
        {"text": text, "reason": reason or "proposta da agente"},
    )
    return f"In review: {item.item_id} (decidi con `talamus review`)."


@server.tool()
def review_list() -> str:
    """Le decisioni in attesa nella coda di review del brain."""
    from talamus.review import ReviewQueue

    pending = ReviewQueue(_paths()).list(status="pending")
    if not pending:
        return "Coda di review vuota."
    return "\n".join(f"- {i.item_id} [{i.kind}] {i.title}" for i in pending)


@server.tool()
def review_apply(item_id: str) -> str:
    """Applica un elemento della coda di review (le correzioni vengono scritte
    nel brain preservando la storia)."""
    from talamus.correct import apply_proposed_correction
    from talamus.review import ReviewQueue

    queue = ReviewQueue(_paths())
    entry = queue.get(item_id)
    if entry is None:
        return f"Nessun elemento: {item_id}"
    if entry.kind == "correction" and not apply_proposed_correction(_paths(), entry.detail):
        return f"Impossibile applicare: nota '{entry.detail.get('title')}' non trovata."
    applied = queue.apply(item_id)
    return f"Applicato: {item_id}" if applied else f"'{item_id}' non è in attesa."


@server.tool()
def review_reject(item_id: str, reason: str = "") -> str:
    """Rifiuta un elemento della coda di review (la decisione resta registrata)."""
    from talamus.review import ReviewQueue

    rejected = ReviewQueue(_paths()).reject(item_id, reason)
    return f"Rifiutato: {item_id}" if rejected else f"'{item_id}' non è in attesa."


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
