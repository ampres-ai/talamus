# Kortex — Roadmap di Esecuzione (completa & vivente)

**Data:** 2026-06-08 · **Stato:** documento **vivo** — è *la* guida dello sviluppo da qui in avanti, si aggiorna man mano. · **Branch corrente:** `feat/traguardo-1-text-loop` (T1, ~72 test verdi).

Questo è l'**indice operativo esaustivo**: ogni implementazione futura, organizzata e in **ordine di esecuzione**. Non è il design delle singole feature — ogni traguardo da **Fase B** in poi avrà il suo **brainstorm → spec → piano → build → test** prima del codice. Le fasi sono la spina d'ordine primaria; in pratica si possono **interlacciare**. Visione di lungo periodo: `2026-05-29-kortex-product-vision.md`; idee fuori scope: `kortex-future-evolutions.md`.

**Legenda stato:** ✅ fatto · 🔜 prossimo · ⏳ dopo. **Ogni voce:** *cosa — perché* (e *fatto quando* dove serve).

---

## 0. Perché esistiamo (posizionamento)

Memoria con tre proprietà che gli altri non hanno **insieme**: **TEMPO** (grafo bitemporale, invalida-non-cancella), **SIGNIFICATO** (ontologia tipizzata auto-emergente per il ragionamento dell'LLM), **VERIFICABILITÀ** (provenienza attiva: torna alla fonte e correggi). Più il cuneo **memoria per agenti**.

Competitor di riferimento: **github.com/nashsu/llm_wiki** (~10.7k stelle, stessa tesi, più avanti come prodotto, ma: niente versioning/cancella-a-cascata, grafo statistico non tipizzato, provenienza passiva). Da loro **rubiamo** le idee buone (overview/index, budget di contesto, citazioni numerate, cache incrementale per hash, agent skill pronta) e le facciamo **tipizzate e temporali**. **Principi fermi:** local-first; l'LLM ragiona e sceglie; il grafo è un indice, non la verità; core stdlib + adapter opzionali; il merge finale è di Giovanni.

---

## Stato attuale — baseline T1 (✅ già fatto)

Per orientarsi, ciò che **esiste già** e su cui costruiamo: ingest testo/Markdown → estrazione LLM (adapter claude-cli) in **schede-concetto** con provenienza, prosa connessa e **wikilink** risolti → cache **ibrida** (Markdown vista umana + JSON verità macchina) → indici **grafo + BM25 + ontologia L1** (relazioni tipizzate, `neighbors`) → **risposte citate** (`ask`). Lato agente: **MCP** read (`search/read_note/recall/neighbors`) + **cattura** (`remember`, hook `SessionEnd`). Merge cross-fonte. CLI: `init/status/doctor/reindex/ingest/ask/search/read/recall/neighbors/remember`. ~72 test (solo Windows finora).

---

## T0 — Merge di T1 *(azione di Giovanni)* 🔜
- **0.1** Rivedere il branch, suite completa, merge in `main`, CHANGELOG. Da qui ogni traguardo nasce/muore sul suo branch.

---

# FASE A — Fondamenta & prodotto usabile
*Rendere pulito, installabile, documentato e adottabile ciò che già funziona, prima delle feature grosse.*

## A0 — Rebrand Kortex → Talamus *(primo traguardo dopo il merge di T1; prima di README/onboarding/docs e di ogni pubblicazione)*
> Motivo: "Kortex" è già il nome di un altro prodotto in un ambito simile. Nuovo nome **Talamus** (il talamo: lo snodo cerebrale che *instrada* le informazioni alla corteccia — calzante per un router di memoria). CLI = `talamus`.
- **A0.1** **Nome repo** — **`talamus_wiki`** (deciso 2026-06-08: brand pulito e indipendente).
- **A0.2** **Package & import** — `src/kortex/` → `src/talamus/`, tutti gli import, classi (`KortexPaths`→`TalamusPaths`, ecc.).
- **A0.3** **CLI & entrypoint** — comando `kortex`→`talamus`; `pyproject` (name + script `talamus`/`talamus-mcp` + extra); nome del server MCP.
- **A0.4** **Config & dati** — `kortex.json`→`talamus.json`, cache `.kortex/`→`.talamus/`, env `KORTEX_*`→`TALAMUS_*`, script hook.
- **A0.5** **Stringhe & branding** — messaggi CLI, prompt, docstring, intestazioni dei documenti (inclusa questa roadmap).
- **A0.6** **Repo & workspace** — rinomina repo; aggiorna `CLAUDE.md`/`AGENTS.md` (riferimenti a `kortex`/`src/kortex/`); opzionale rinomina cartella locale `C:\dev\Kortex`→`Talamus`.
- **A0.7** **Disponibilità nome** — verifica PyPI `talamus`, GitHub e dominio; se occupato, valuta un suffisso.
- **A0.8** **Test** — rinomina `tests/test_kortex_*`→`test_talamus_*`, suite verde.
- **A0.9** **Migrazione** — pre-release: nessuna retro-compatibilità necessaria; opzionale migrazione one-shot dei brain locali `.kortex/`→`.talamus/`.

## A1 — Salute del codice
*Premessa onesta: il codice è già piccolo e modulare (~1.600 righe, file max `cli.py` 197): professionalizzazione, non salvataggio.*
- **A1.1** Tooling qualità — `ruff` (lint+format) + type-checker, un comando unico lint+type+test.
- **A1.2** CI multi-OS — GitHub Actions Win/mac/Linux su 3.13, gate sulle PR. *Oggi testato solo su Windows.*
- **A1.3** Type hints completi + docstring su ogni API pubblica (cosa/come/dipendenze).
- **A1.4** Documento di architettura interna + diagramma del flusso dati.
- **A1.5** Gerarchia di eccezioni + messaggi d'errore **azionabili** (brain non init, motore assente, fonte mancante, cache corrotta).
- **A1.6** Pulizia residui — codice morto/esperimenti revertiti, naming uniforme, niente import inutili.
- **A1.7** Logging strutturato, silenzioso di default (`--verbose`/`KORTEX_LOG`).
- **A1.8** Scrivere i **file-fonte normalizzati** su disco (oggi la provenance punta solo al raw). *Prerequisito di B5/verificabilità.*
- **A1.9** Versioning dello schema della cache + **migrazioni** (la cache è ricostruibile, ma i formati vanno versionati).
- **A1.10** Harness di **benchmark/perf** formalizzato (i miei script di misura → suite riproducibile: token, recall, tempi).
- **A1.11** Baseline di **sicurezza** — permessi dei file locali, revisione della superficie MCP (cosa si espone), niente segreti nei log.
- **A1.12** Sistema di **config** chiaro — schema `kortex.json`, variabili d'ambiente, precedenza, validazione.

## A2 — CLI facilissima (prima della UI)
- **A2.1** `kortex` senza argomenti → pannello: stato brain + cosa fare ora + prossimo comando.
- **A2.2** `kortex init` guidato — rileva motori, propone, scrive config, crea cartelle, offre demo.
- **A2.3** `kortex doctor` potenziato — motore, salute brain/cache, integrazioni; per ogni problema **il comando** che lo risolve.
- **A2.4** Output `ask` curato (risposta + citazioni + fonti cliccabili) e `--json`.
- **A2.5** Progresso su `ingest` (file, n. schede, wikilink, tempo).
- **A2.6** Help eccellente con esempi reali per comando + `kortex quickstart`.
- **A2.7** `--json`/`--quiet` su tutti i comandi di lettura.
- **A2.8** Completion shell (bash/zsh/PowerShell).
- **A2.9** Scoping **globale + progetto** (brain locale vs personale; `--global`).
- **A2.10** Gestione **brain multipli** (`list/create/switch/delete`).
- **A2.11** UX di `reindex`/rebuild (incrementale, messaggi chiari, dry-run).
- **A2.12** `export`/`import` di un brain (portabilità).

## A3 — Motori LLM (adapter)
- **A3.1** Provider **Ollama** (locale).
- **A3.2** Provider **API key** (Anthropic/OpenAI).
- **A3.3** Provider **Gemini** (CLI / API).
- **A3.4** Provider **Codex**.
- **A3.5** **Auto-detect + selezione** (config `kortex.json` / `--engine`); i tre modi della visione.
- **A3.6** Output in **streaming** (UX di attesa).
- **A3.7** **Retry/timeout/errori** uniformi tra provider.
- **A3.8** Tracciamento **uso/costo** per motore.
- **A3.9** Parametri modello (context window, temperatura) configurabili.

## A4 — Onboarding 10 minuti & distribuzione (connesso a tutto, ogni piattaforma)
- **A4.1** `pipx install kortex` documentato.
- **A4.2** **Binari standalone** (PyInstaller) per chi non ha Python, Win/mac/Linux.
- **A4.3** `kortex mcp install` — config in un comando per Claude Code/Cursor/Claude Desktop.
- **A4.4** `kortex hook install` — hook `SessionEnd` in un comando.
- **A4.5** Integrazione **Obsidian** documentata (apri `notes/` come vault; wikilink/anteprime).
- **A4.6** `kortex demo` — brain d'esempio per provare subito.
- **A4.7** Quickstart 10 minuti (doc + GIF/asciinema) dall'install alla prima risposta citata e al primo MCP. *Fatto quando: uno sconosciuto ci riesce in ≤10 min.*
- **A4.8** Verifica cross-platform reale (Win/mac/Linux).

## A5 — README da repository importante
- **A5.1** Hero — valore in una riga + i 3 differenziatori + GIF.
- **A5.2** **Tabella di posizionamento** onesta (Kortex vs RAG vs llm_wiki vs Zep/mem0).
- **A5.3** Quickstart (install→init→ingest→ask) + MCP.
- **A5.4** Diagramma architettura.
- **A5.5** Casi d'uso: second brain **e** memoria agenti.
- **A5.6** Sezioni standard + badge CI + link a questa roadmap. *Vende il core + la visione, senza fingere feature non ancora fatte.*

## A6 — Documentazione & community
- **A6.1** Docs utente (concetti, comandi, config, motori, MCP, Obsidian).
- **A6.2** Docs sviluppatore (architettura, modello dati, come aggiungere un adapter, contribuire/testare).
- **A6.3** Sito docs (mkdocs-material) + comando per servirlo in locale.
- **A6.4** CHANGELOG + versioning semantico.
- **A6.5** `CONTRIBUTING`, `CODE_OF_CONDUCT`, template issue/PR.
- **A6.6** Esempi/ricette riproducibili.

---

# FASE B — Conoscenza & recupero (i differenziatori)
*Il cuore. Ogni traguardo: brainstorm→spec→piano→build→test, branch propri.*

## B1 — Consolidamento concetti
- **B1.1** Rilevazione quasi-doppioni (nomi/lingue diverse: *Hybrid search*≡*Ricerca ibrida*, *Reranker/Reranking*, *RAG* duplicata) via alias/relazioni/sovrapposizione + check LLM leggero.
- **B1.2** Fusione guidata in scheda canonica (riusa `merge_notes`) con **coda di revisione**.
- **B1.3** Riallineo ontologia/grafo/wikilink (nessun link rotto).

## B2 — Qualità del recupero (base)
- **B2.1** **Lemmatizzazione italiana** per BM25/keyword (il bench ha mostrato *spezzare*≠*spezza* → chunking mancato).
- **B2.2** **Espansione della query** — l'LLM riscrive la domanda vaga in termini/sinonimi prima di cercare.
- **B2.3** Stadio di **reranking** dei candidati.
- **B2.4** **Set di valutazione** + harness `recall@k`/precision — misurare, non indovinare (sblocca il graph-routing serio).
- **B2.5** **Budget di contesto** (quota wiki/chat/index/sistema).

## B3 — Overview gerarchico (tipizzato + temporal-aware) *(il centro)*
*Quadro di tutta la memoria con costo per domanda ~logaritmico, non lineare.*
- **B3.1** **Induzione domini** dal grafo + ontologia tipizzata; l'LLM nomina/descrive i domini a indicizzazione. **MVP: un livello.**
- **B3.2** Artefatti **`overview`** (mappa domini, ~costante) + **`index`** (catalogo), aggiornati a reindex.
- **B3.3** Motore unico **`answer(domanda, storico=[])`**: overview→scegli dominio→drill-down→scegli ingresso→leggi→naviga ontologia/wikilink→risposta citata.
- **B3.4** Superfici sullo stesso motore: `ask`, MCP `overview`/`map`, predisposizione **chat UI** (storico).
- **B3.5** **Embedding** come adapter **opzionale** (via Ollama), **spento di default** — rete di sicurezza sull'ingresso.
- **B3.6** **Predisposizione temporale** di domini/schede → B4 estende senza rifacimenti.
- **B3.7** **Albero multi-livello** (oltre ~qualche migliaio di schede): split in sotto-domini. ⏳

## B4 — Grafo bitemporale + invalidazione *(il moat)*
- **B4.1** Modello bitemporale (valid-time + transaction-time) su fatti/relazioni.
- **B4.2** **Invalida-non-cancella** — la contraddizione chiude il fatto vecchio (non più valido da T).
- **B4.3** **Query temporali** ("cosa era vero al tempo T?", "com'è cambiato?").
- **B4.4** Note che non si spostano; overlay temporale/ontologico **ricostruibile**.
- **B4.5** Integrazione retrieval — di default verità **corrente**, passato interrogabile e **citabile**.

## B5 — Correzione-da-fonte (provenienza attiva)
- **B5.1** Rilevazione **dubbio** durante un ask (bassa confidenza/contraddizione).
- **B5.2** **Verifica alla fonte** conservata (raw + normalizzata).
- **B5.3** **Correzione tracciata** nel modello bitemporale (la vecchia versione resta passato).
- **B5.4** **Coda di revisione** per le correzioni a bassa confidenza.

## B6 — Ontologia avanzata
- **B6.1** **Coda di revisione** delle proposte di relazione/ontologia.
- **B6.2** **Confidenza** delle relazioni + pruning del rumore.
- **B6.3** Ontologia condivisa **cross-brain**. ⏳

---

# FASE C — Sorgenti (ingestion di ogni formato)
*Recuperare ampiezza d'input. Ordine per valore/diffusione. Ogni formato: estrazione + provenienza con locator (pagina/sezione/timestamp).*
> Nota d'ordine: **C1.1 (PDF testo)** è table-stakes; valutare se anticiparlo in Fase A per l'adozione. Il resto segue i differenziatori.

## C1 — Documenti
- **C1.1** **PDF** (testo nativo).
- **C1.2** **OCR** per PDF scansionati / immagini con testo.
- **C1.3** **DOCX**.
- **C1.4** **PPTX**.
- **C1.5** **XLSX / CSV** (tabellari).
- **C1.6** **EPUB** / ebook.

## C2 — Web & cattura
- **C2.1** **URL** → fetch + estrazione leggibile (Readability).
- **C2.2** **Estensione browser** — clip della pagina corrente nel brain.
- **C2.3** **RSS/feed** + **auto-watch** sorgenti (rileva modifiche esterne).
- **C2.4** Cattura da **clipboard**.

## C3 — Conversazioni & email
- **C3.1** **Export chat LLM** (ChatGPT/Claude) come fonte.
- **C3.2** **Email** (mbox/eml).
- **C3.3** Export **Slack/WhatsApp**.

## C4 — Media
- **C4.1** **Immagini** → captioning con LLM di visione.
- **C4.2** **Audio** → trascrizione (memo vocali, podcast).
- **C4.3** **Video** → sottotitoli/trascrizione.

## C5 — Codice
- **C5.1** File di codice singoli.
- **C5.2** **Repository/codebase** (struttura + simboli come contesto).

## C6 — Pipeline di ingest (trasversale ai formati)
- **C6.1** **Cache incrementale per hash** (SHA) — non ri-processare l'invariato.
- **C6.2** **Auto-watch** delle sorgenti.
- **C6.3** **Import bulk/cartella** ricorsivo (path come contesto).
- **C6.4** **Provenienza con locator** per formato (pagina, sezione, timestamp).
- **C6.5** **Coda di ingest** persistente e resiliente ai crash (serializza le chiamate LLM).

---

# FASE D — Interfacce & ecosistema

## D1 — UI Kortex
- **D1.1** **Chat-sulla-memoria** sullo **stesso** motore `answer(...)`.
- **D1.2** **Effetto-Wikipedia** — anteprima all'hover dei wikilink.
- **D1.3** **Navigazione per domini** (overview di B3 sfogliabile).
- **D1.4** **Editor** delle note (con reindex dei campi umani).
- **D1.5** **UI delle code di revisione** (consolidamenti, correzioni, proposte d'ontologia).

## D2 — Visualizzazione del grafo
- **D2.1** Grafo **tipizzato + temporale** (ispirato alla loro sigma.js, ma con i nostri tipi e tempo).
- **D2.2** **Insight** — cluster, lacune, note isolate, connessioni sorprendenti.

## D3 — Accesso esteso & integrazioni
- **D3.1** **HTTP API** locale.
- **D3.2** **Endpoint MCP remoto autenticato** (LLM da browser; sola-lettura + auth) — vedi future-evolutions.
- **D3.3** **Plugin Obsidian** (anteprime/azioni native).
- **D3.4** **Agent skill** pronta (pacchetto per Claude Code/altri agenti).

---

# FASE E — Scala, sicurezza, operatività
- **E1** Multi-brain & scoping avanzato (personale/progetto/team).
- **E2** Backup/restore + export/import (già in A2.12 per il singolo brain; qui automazione).
- **E3** **Cifratura a riposo** (opzionale) per brain sensibili.
- **E4** Performance & memoria **a scala** (centinaia di migliaia di note).
- **E5** **Telemetria opt-in**, privacy-first (di default spenta).
- **E6** Garbage collection / compattazione della cache.
- **E7** Concorrenza / lock (edit simultanei umano+agente).
- **E8** Automazione delle **release** (build, firma, pubblicazione multi-OS).

---

# Agent-memory (il cuneo) — approfondimento trasversale
*Distribuito tra le fasi, ma tenuto a fuoco perché è un differenziatore di mercato.*
- ✅ recall/read + remember/capture + gate euristico + hook.
- 🔜 **Dedup/merge cross-sessione** (più sessioni sullo stesso tema → una scheda).
- 🔜 **Scoping per agente/progetto** (memoria separata o condivisa).
- ⏳ Review "**cosa ha imparato l'agente**" prima di consolidare.
- ⏳ **Agent skill** pacchettizzata (D3.4).

---

## Cross-cutting (a ogni traguardo)
Test verdi · **CI verde sui 3 OS** · `docs/`+README+CHANGELOG aggiornati col codice · nessun wikilink/test rotto · da Fase B in poi ogni traguardo ha il suo **brainstorm→spec→piano** prima del codice.

## Fuori scope per ora
Vedi `kortex-future-evolutions.md` (endpoint remoto in dettaglio; graph-routing con set di valutazione; ecc.). Si tirano dentro quando il valore lo giustifica.
