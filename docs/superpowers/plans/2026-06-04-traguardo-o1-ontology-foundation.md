# Traguardo O1 — Fondazione dell'ontologia (Livello 1)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** La base deterministica dell'ontologia auto-emergente: i concetti sono unificati (niente doppioni), le relazioni hanno un tipo normalizzato, e la mappa è navigabile (vicini di un concetto). È la fondazione su cui costruire il Livello 2 (categorie/domini auto-indotti, modello bi-temporale, contraddizioni), che resta fuori da questo cut.

**Architecture:** Un nuovo indice derivato `ontology.json` in `.talamus/cache/`, costruito dalle note. Le note SONO i concetti canonici; i bersagli di relazioni e wikilink vengono **risolti al concetto canonico** tramite il registro (titoli + alias), così "RAG" e "Retrieval-Augmented Generation" diventano lo stesso nodo. I tipi di relazione sono normalizzati in un vocabolario controllato ma estendibile. Navigazione esposta via SDK, CLI e MCP. Deterministico: nessuna nuova chiamata LLM.

**Tech Stack:** Python 3.13, `unittest`. Solo libreria standard.

**Fuori scope (cut successivi dell'ontologia):** induzione automatica di categorie/domini, modello bi-temporale (valido_da/a) e invalidazione delle contraddizioni stile Zep, coda di revisione delle proposte di ontologia, riorganizzazioni di schema. Il modello-dati li prevede già (campi temporali su `Relation`, entità concetto/categoria/dominio) — qui costruiamo solo la base.

---

### Task 1: Vocabolario e normalizzazione delle relazioni

**Files:** Create `src/talamus/ontology.py`; Test `tests/test_talamus_ontology.py`.

- `RELATION_TYPES`: insieme controllato (`uses`, `is-a`, `part-of`, `contrasts-with`, `depends-on`, `related`).
- `normalize_relation(rel: str) -> str`: mappa per parole chiave (es. "usa/uses" → uses; "è un tipo di/is a/is-a" → is-a; "parte di/part of" → part-of; "a differenza/contrasts" → contrasts-with; "dipende/depends" → depends-on); sconosciuto → `related`.

TDD: varianti italiane/inglesi mappate ai tipi giusti; ignoto → related.

### Task 2: Costruzione dell'ontologia + vicini

**Files:** Modify `src/talamus/ontology.py`; Test `tests/test_talamus_ontology.py`.

- `build_ontology(notes) -> dict`: `{"concepts": {title: {aliases, tags}}, "edges": [{source, type, target}]}`. I concetti sono i titoli delle note. Per ogni `relation` e `proposed_link` di una nota, **risolvi il target** contro un `NoteRegistry` (titoli + alias) al titolo canonico; se risolto, aggiungi un arco tipizzato `source_title -[type]-> target_title` (tipo via `normalize_relation`); se non risolto, ignora in questo cut (sarà un "concetto mancante" per la review, in L2).
- `neighbors(ontology, concept_title) -> list[dict]`: vicini tipizzati (uscenti ed entranti): `{title, relation, direction}`. Match del titolo case-insensitive.

TDD: due note con una relazione "usa" + un alias → un arco `uses` verso il titolo canonico; `neighbors` li restituisce nei due versi; relazione verso un concetto inesistente → nessun arco.

### Task 3: Persistenza nella cache

**Files:** Modify `src/talamus/paths.py`, `src/talamus/store.py`; Test `tests/test_talamus_store.py`.

- `TalamusPaths.ontology_file` → `.talamus/cache/ontology.json`.
- In `rebuild_indexes`: costruisci e salva l'ontologia accanto a grafo/BM25.
- `load_ontology(paths) -> dict` in `ontology.py`.

TDD: dopo `rebuild_indexes`, `ontology_file` esiste ed è interrogabile con `neighbors`.

### Task 4: Navigazione esposta (SDK + CLI + MCP)

**Files:** Modify `src/talamus/recall.py`, `src/talamus/cli.py`, `src/talamus/mcp_server.py`; Test relativi.

- `recall.concept_neighbors(paths, concept) -> list[dict]`: carica l'ontologia e chiama `neighbors`.
- CLI `talamus neighbors <concetto> --root`: stampa i vicini tipizzati.
- MCP tool `neighbors(concept)`: l'agente naviga la mappa (è il livello "fai il bibliotecario").

TDD: CLI restituisce i vicini dopo un ingest; il set dei tool MCP include `neighbors`.

### Task 5: Verifica completa

- Suite intera verde. (La prova d'uso reale approfondita la fa l'utente dopo.)

---

## Self-Review

- Concetti unificati: Task 2 (risoluzione via registro).
- Relazioni tipizzate: Task 1, 2.
- Mappa navigabile (vicini): Task 2, 4.
- Indice derivato ricostruibile: Task 3.
- L2 (categorie/domini/bi-temporale/contraddizioni) esplicitamente rinviato.
