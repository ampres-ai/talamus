# Traguardo C1 — MCP Recall (primo cut della memoria-per-agenti)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Dare agli agenti (Claude Code) la possibilità di LEGGERE dal brain Talamus durante una sessione, tramite un server MCP locale con tre strumenti: `search`, `read_note`, `recall`.

**Architecture:** Una sottile SDK di lettura (`talamus/recall.py`) costruita sul recupero esistente (graph-first + BM25 + `build_context_bundle`). Un server MCP (`talamus/mcp_server.py`) basato sull'SDK ufficiale `mcp` (FastMCP) che espone le tre funzioni come strumenti. L'SDK `mcp` è una **dipendenza opzionale** (`pip install talamus[mcp]`): il core resta senza dipendenze. Solo lettura, nessuna scrittura.

**Tech Stack:** Python 3.13, `unittest`, `mcp` (FastMCP, extra opzionale), trasporto stdio.

**Fuori scope (prossimi cut di C):** `remember`/cattura, hook di Claude Code, source type "sessione", compressione tool-log, gate a soglie, strumenti di scrittura, `graph_neighbors`, ambito globale+progetto.

---

### Task 1: SDK di lettura (`recall.py`)

**Files:** Create `src/talamus/recall.py`; Test `tests/test_talamus_recall.py`.

- `search_notes(paths, query, limit=5) -> list[dict]`: candidati graph-first, fallback BM25; ogni dict = {title, summary}.
- `read_note_text(paths, title) -> str | None`: contenuto Markdown della scheda (match per filename, fallback case-insensitive sul titolo).
- `recall_context(paths, question, limit=5) -> str`: usa `build_context_bundle` e ritorna `bundle.render()` (contesto, non risposta confezionata: l'agente è l'LLM).

TDD: costruire un brain (write_note + rebuild_indexes), poi verificare i tre comportamenti, incluso "niente risultati".

### Task 2: Packaging dell'extra MCP

**Files:** Modify `pyproject.toml`.

- `[project.optional-dependencies] mcp = ["mcp>=1.0"]`.
- `[project.scripts] talamus-mcp = "talamus.mcp_server:main"`.
- Verifica: `tomllib` legge nome script e dipendenza.

### Task 3: Server MCP (`mcp_server.py`)

**Files:** Create `src/talamus/mcp_server.py`; Test `tests/test_talamus_mcp_server.py`.

- FastMCP("talamus") con tre `@server.tool()`: `search`, `read_note`, `recall`, ciascuno chiama `recall.py`.
- Root del brain da `--root` (default `.`) in `main()`, poi `server.run()` (stdio).
- Import isolato di `mcp` dentro il modulo, così importarlo senza l'extra dà un errore chiaro, e il resto del pacchetto non dipende da `mcp`.
- TDD: test `skipUnless(mcp installato)` che importa il modulo e verifica che i tre strumenti siano registrati.

### Task 4: Smoke reale + configurazione Claude Code

**Files:** Modify `README.md` (sezione "Connettere a Claude Code").

- Smoke: avviare il server e, con un client MCP stdio in-process, elencare gli strumenti e chiamare `search` su un brain di prova.
- Documentare lo snippet `.mcp.json` per Claude Code:
  `{"mcpServers":{"talamus":{"command":"talamus-mcp","args":["--root","<path-al-brain>"]}}}`.

---

## Self-Review

- Recall-first, solo lettura: Task 1, 3.
- MCP come extra opzionale, core senza dipendenze: Task 2, 3 (import isolato).
- Riuso del recupero esistente: Task 1.
- Tipi coerenti: `search_notes/read_note_text/recall_context(paths, ...)` usati dai tre strumenti.
