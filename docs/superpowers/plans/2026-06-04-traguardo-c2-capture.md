# Traguardo C2 — Cattura delle sessioni (lato scrittura della memoria-agenti)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Chiudere il giro *leggi → lavora → ricorda*: le sessioni di lavoro degli agenti (transcript + git diff) diventano note nel brain, con un gate a soglie per il costo e un tool MCP `remember`, più uno script hook per la cattura automatica.

**Architecture:** Un nuovo "source type sessione": `session.py` comprime meccanicamente il transcript (niente LLM) e produce un `NormalizedPackage` che passa per l'estrattore esistente. Un gate euristico decide se vale la pena. `remember_session` orchestra (gate → archivia raw → normalizza → compila), riusando il core di `ingest`. Esposto via CLI `talamus remember` e via MCP `remember`. Uno script hook Claude Code (`Stop`/`SessionEnd`) cattura e chiama `remember`.

**Tech Stack:** Python 3.13, `unittest`, `mcp` (extra), `claude-cli` per l'estrazione.

**Decisioni del cut:**
- Cattura = **transcript + git diff**.
- Gate = **euristico, senza LLM**: vale se c'è un diff non vuoto OPPURE il transcript supera una soglia di caratteri.
- Compressione = **meccanica** (parse JSONL/testo, comprimi i blocchi tool in una riga, tieni i turni significativi). Il giudizio di valore resta all'estrattore.
- `remember` sincrono nel primo cut (l'agente/hook aspetta la compilazione); l'asincronia è una rifinitura futura.

**Fuori scope:** ambito globale+progetto automatico, dedup avanzata cross-sessione, async/queue, formati transcript non-Claude.

---

### Task 1: Normalizzatore di sessione + compressione transcript

**Files:** Create `src/talamus/session.py`; Test `tests/test_talamus_session.py`.

- `compress_transcript(text: str) -> str`: se il testo è JSONL (righe JSON con ruolo/contenuto), estrae i turni utente/assistente e **comprime i blocchi tool** in righe compatte (es. `[tool Edit: auth.py]`); altrimenti passthrough ripulito.
- `normalize_session(raw_path: str, transcript: str, diff: str) -> NormalizedPackage`: produce sezioni `conversazione` (transcript compresso) e, se presente, `modifiche` (il diff), con hash/provenienza. Riusa `NormalizedSection`/`NormalizedPackage`.

TDD: JSONL con tool-call → compresso; testo semplice → passthrough; pacchetto con sezione modifiche quando c'è un diff.

### Task 2: Gate euristico

**Files:** Modify `src/talamus/session.py`; Test `tests/test_talamus_session.py`.

- `session_worth_remembering(transcript: str, diff: str, min_chars: int = 400) -> bool`: True se `diff.strip()` non vuoto OPPURE `len(transcript) >= min_chars`. Niente LLM.

TDD: sessione con diff → True; transcript lungo senza diff → True; chiacchiera breve senza diff → False.

### Task 3: Core condiviso di compilazione + `remember_session`

**Files:** Modify `src/talamus/ingest.py`; Test `tests/test_talamus_ingest.py`.

- Estrai `_compile_package(paths, package, llm) -> int`: `extract_notes` → `write_note_json` per tutte → render con registro dell'intero lotto → `rebuild_indexes`. `ingest_file` lo usa.
- `remember_session(paths, transcript, diff, llm) -> dict`: applica il gate; se non vale ritorna `{"skipped": True}`; altrimenti archivia raw (transcript + diff), `normalize_session`, `_compile_package`. Ritorna `{"notes_written": n, "skipped": False}`.

TDD: sessione valida (con FakeLLM) → note scritte; sessione banale → skipped.

### Task 4: CLI `talamus remember`

**Files:** Modify `src/talamus/cli.py`; Test `tests/test_talamus_cli.py`.

- `talamus remember --transcript <file> [--diff <file>] --root <brain>`: legge i file, chiama `remember_session` col provider LLM (default claude-cli, iniettabile nei test). Stampa il riepilogo (incl. "saltata" se gated out).

TDD: con FakeLLM, remember di una sessione valida → exit 0 + note; sessione banale → exit 0 + "saltata".

### Task 5: Tool MCP `remember`

**Files:** Modify `src/talamus/mcp_server.py`; Test `tests/test_talamus_mcp_server.py`.

- `@server.tool() remember(text: str) -> str`: l'agente salva un'intuizione al volo. Normalizza `text` (riusa `normalize_text`) e compila (`_compile_package`) col provider LLM. Ritorna un riepilogo.
- Il server ora usa anche un LLM provider (claude-cli) per `remember`; resta opzionale (solo extra mcp).

TDD: il set di tool registrati include `remember` (oltre a search/read_note/recall).

### Task 6: Script hook Claude Code + documentazione

**Files:** Create `scripts/talamus-session-hook.py`; Modify `README.md`.

- Script che legge il transcript della sessione (path fornito dall'hook) + esegue `git diff` nella repo, poi chiama `talamus remember`. Best-effort, non blocca in caso d'errore.
- README: come registrare l'hook `Stop`/`SessionEnd` in Claude Code che lancia lo script.

### Task 7: Verifica completa + smoke reale

**Files:** none salvo difetti.

- Suite completa verde.
- Smoke: una sessione di esempio (transcript JSONL + diff) → `talamus remember` reale (claude-cli) → leggere le note generate e giudicarne il valore (Scommessa A lato sessioni).

---

## Self-Review

- Source type sessione + compressione: Task 1.
- Gate a soglie: Task 2.
- remember (CLI + MCP): Task 4, 5.
- Hook: Task 6.
- transcript+diff: Task 1, 3.
- Riuso del core ingest (DRY): Task 3.
