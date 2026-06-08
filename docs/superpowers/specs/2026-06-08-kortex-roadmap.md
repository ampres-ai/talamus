# Kortex — Roadmap di Esecuzione (dettagliata)

**Data:** 2026-06-08 · **Stato:** vivo (si aggiorna man mano) · **Branch corrente:** `feat/traguardo-1-text-loop` (T1, ~72 test verdi, punto di merge naturale).

Questo documento è l'**indice operativo** di tutto ciò che resta da fare, in **ordine di esecuzione**, con ogni voce spiegata (cosa, perché, e — dove utile — *fatto quando*). Non è il design di ogni singola feature: ogni traguardo da **F1** in poi avrà il suo ciclo **brainstorm → spec → piano → build → test** prima del codice. La visione di lungo periodo sta in `2026-05-29-kortex-product-vision.md`; le idee deliberatamente fuori scope in `kortex-future-evolutions.md`.

---

## 0. Perché questa roadmap esiste (posizionamento)

**Perché Kortex esiste** — la nostra ragione d'essere è una memoria con tre proprietà che gli altri non hanno insieme:

- **TEMPO** — un grafo **bitemporale**: non perdiamo mai una verità passata, e sappiamo *cosa era vero al tempo T*. Le contraddizioni **invalidano**, non cancellano.
- **SIGNIFICATO** — un'**ontologia tipizzata** auto-emergente (usa / è-un / parte-di / contrasta-con / dipende-da): l'LLM ragiona sul *tipo* di legame, non solo su "queste pagine sono vicine".
- **VERIFICABILITÀ** — **provenienza attiva**: la fonte è sempre conservata e, in caso di dubbio durante un ask, si torna alla fonte e si **corregge** la nota.

Più un **cuneo**: la **memoria per gli agenti**, che ha bisogno proprio di verità corrente, citabile e ragionata.

**Il contesto competitivo (onesto).** `github.com/nashsu/llm_wiki` (≈10.7k stelle) fa la nostra stessa tesi (il "LLM Wiki" di Karpathy) ed è **più avanti come prodotto**: app desktop, UI con grafo, ingest multi-formato, pipeline di recupero completa, community detection, `overview.md` auto-aggiornato. **Non li battiamo sulla polish a breve.** Ma hanno un soffitto preciso che coincide con i nostri tre differenziatori: **niente versioning** (cancellano a cascata → perdono il passato), grafo di **rilevanza statistica** (non ontologia tipizzata per il ragionamento), provenienza **passiva** (tracciano e cancellano, non correggono). La nostra strategia non è "lo stesso wiki un filo meglio" — è **memoria con tempo, significato e verificabilità**. Da loro **rubiamo** senza vergogna le idee buone (overview/index, budget di contesto, citazioni numerate, cache incrementale) e le facciamo **tipizzate e temporali**.

**Principi fermi** (non si rinegoziano senza una buona ragione): local-first; l'LLM **ragiona e sceglie**; il grafo è un **indice**, non la verità; **core stdlib + adapter opzionali**; il merge finale è di Giovanni.

---

## Traguardo 0 — Merge di T1  *(azione di Giovanni)*

- **0.1 Merge del text-loop.** Rivedere il branch, eseguire l'intera suite, fondere in `main`. T1 (testo → estrazione in schede con provenienza → grafo/BM25/ontologia → risposte citate + lato agente MCP read & capture) è una milestone pulita e testata. *Fatto quando:* `main` contiene T1, CHANGELOG aggiornato. Da qui in poi ogni traguardo nasce e muore sul suo branch.

---

# FASE A — Fondamenta & prodotto usabile

*Rendere pulito, installabile, documentato e adottabile ciò che **già funziona**, prima di impilarci sopra le feature grosse. Così il flywheel di feedback/stelle parte subito e le feature nascono su basi solide.*

## Traguardo A1 — Salute del codice

> Premessa onesta: il codice è già piccolo e modulare (~1.600 righe, file max `cli.py` 197). Questo non è un salvataggio, è una **professionalizzazione**.

- **A1.1 Tooling qualità.** `ruff` (lint+format) + type-checker (`mypy`/`pyright`), più un comando unico (`kortex-dev` o `make check`) che fa lint+type+test. *Perché:* uno standard solo, errori presi prima. *Fatto quando:* un comando dà tutto verde.
- **A1.2 CI multi-OS.** GitHub Actions su Windows + macOS + Linux con Python 3.13, gate obbligatorio sulle PR (lint+type+test). *Perché:* oggi è testato **solo su Windows**. *Fatto quando:* badge verde sui tre OS.
- **A1.3 Type hints + docstring.** Tipi completi e docstring su ogni funzione pubblica (cosa fa, come si usa, da cosa dipende). *Fatto quando:* type-check pulito, moduli pubblici documentati.
- **A1.4 Documento di architettura interna.** Responsabilità di ogni modulo + diagramma del flusso dati (ingest → schede → cache → retrieval → answer). *Perché:* chiunque (incluso un agente) capisce i confini senza leggere tutto il codice. *Fatto quando:* `docs/architecture.md` allineato al codice.
- **A1.5 Gestione errori coerente.** Una gerarchia di eccezioni Kortex e messaggi **azionabili** per i casi comuni: brain non inizializzato, motore LLM non configurato/non trovato, fonte mancante, cache corrotta. *Fatto quando:* ogni errore noto dice anche *il prossimo passo*.
- **A1.6 Pulizia residui.** Rimuovere codice morto/esperimenti revertiti, uniformare il naming, togliere helper duplicati. *Fatto quando:* nessun import inutilizzato, naming coerente in tutto il package.
- **A1.7 Logging strutturato.** Silenzioso di default, verboso con `--verbose`/`KORTEX_LOG`. *Perché:* diagnosticare senza rumore.
- **A1.8 Correttezza provenienza.** Scrivere davvero i **file-fonte normalizzati** su disco (oggi la provenance punta solo al raw). *Perché:* la correzione-da-fonte (F4) e la verificabilità ne dipendono. *Fatto quando:* ogni scheda ha fonte raw **e** normalizzata accessibili.

## Traguardo A2 — CLI facilissima (prima della UI)

*La CLI è l'unica interfaccia finché non c'è la UI: deve essere a prova di neofita.*

- **A2.1 `kortex` senza argomenti.** Pannello amichevole: stato del brain, cosa puoi fare adesso, prossimo comando suggerito. *Perché:* zero attrito al primo avvio.
- **A2.2 `kortex init` guidato.** Rileva i motori presenti (claude-cli/codex/ollama/gemini), propone quello da usare, scrive `kortex.json`, crea le cartelle, offre il brain demo. *Fatto quando:* dall'install al primo `ask` in un minuto.
- **A2.3 `kortex doctor` potenziato.** Verifica motore disponibile, salute del brain/cache, integrazioni (MCP, hook); per ogni problema stampa **il comando** per risolverlo.
- **A2.4 Output di `ask` curato.** Risposta + citazioni numerate + elenco fonti (path cliccabili) nel terminale; `--json` per agenti/script.
- **A2.5 Progresso su `ingest`.** File in corso, n. schede create, wikilink risolti, tempo impiegato.
- **A2.6 Help eccellente.** `--help` con **esempi reali** per ogni comando; `kortex quickstart` che stampa i 5 comandi chiave.
- **A2.7 Modalità output coerenti.** `--json` e `--quiet` su tutti i comandi di lettura (`search/read/recall/ask/neighbors`). *Perché:* scripting e uso da parte degli agenti.
- **A2.8 Completion shell** per bash/zsh/PowerShell.
- **A2.9 Scoping globale + progetto.** Kortex capisce se sei dentro un progetto (brain locale) o usa quello globale; flag `--global`. *Perché:* un brain per progetto **e** uno personale. *Fatto quando:* il brain giusto è risolto in entrambi i casi.

## Traguardo A3 — Onboarding in 10 minuti & distribuzione (connesso a tutto, ogni piattaforma)

- **A3.1 Adapter motori completi + selezione.** Implementare i provider mancanti dietro `LLMProvider`: **Ollama** locale, **API key** (Anthropic/OpenAI), **Gemini** CLI, **Codex**; con auto-detect e scelta via `kortex.json`/`--engine`. *Perché:* "connesso a tutto quello che usiamo" e i tre modi della visione. *Fatto quando:* lo **stesso** `ask` gira almeno su claude-cli, Ollama e API.
- **A3.2 Installazione semplice.** `pipx install kortex` documentato; valutare **binari standalone** (PyInstaller) per chi non ha Python, su Win/mac/Linux. *Fatto quando:* install in un comando su ogni OS.
- **A3.3 Setup MCP in un comando.** `kortex mcp install` genera/inserisce la config per Claude Code / Cursor / Claude Desktop (`.mcp.json`), documentato.
- **A3.4 Hook di cattura in un comando.** `kortex hook install` per il `SessionEnd` di Claude Code (chiude il loop lavora→ricorda).
- **A3.5 Integrazione Obsidian.** Documentare "apri la cartella `notes/` come vault"; verificare wikilink e anteprime.
- **A3.6 Brain demo.** `kortex demo` crea un brain d'esempio per provare subito `ask/search/neighbors`.
- **A3.7 Quickstart 10 minuti.** Documento + GIF/asciinema dall'install alla prima risposta citata e al primo collegamento MCP. *Fatto quando:* uno sconosciuto ci riesce in ≤10 minuti senza chiedere aiuto.

## Traguardo A4 — README da repository importante

- **A4.1 Hero.** Proposta di valore in una riga + i tre differenziatori (Tempo/Significato/Verificabilità) + una GIF.
- **A4.2 Posizionamento onesto.** Tabella **Kortex vs RAG puro vs llm_wiki vs Zep/mem0**: cosa facciamo di diverso (bitemporale, ontologia tipizzata, provenienza attiva, agent-memory). *Perché:* chi arriva capisce **subito** perché esistiamo.
- **A4.3 Quickstart nel README** (install → init → ingest → ask) + come collegare l'MCP.
- **A4.4 Diagramma architettura** (storage ibrido, grafo-come-indice, pipeline).
- **A4.5 Casi d'uso:** second brain umano **e** memoria per agenti.
- **A4.6 Sezioni standard:** feature, link a questa roadmap, contributing, licenza, badge CI.
- *Onestà:* il README vende il **core funzionante + la visione**, senza fingere che bitemporale/overview esistano già.

## Traguardo A5 — Documentazione

- **A5.1 Docs utente:** concetti (scheda, provenienza, ontologia, bitemporale), riferimento comandi, riferimento config, setup motori, setup MCP, uso con Obsidian.
- **A5.2 Docs sviluppatore:** architettura, modello dati, **come aggiungere un adapter LLM**, come contribuire/testare.
- **A5.3 Sito docs** (mkdocs-material) pubblicato; un comando per servirlo in locale.
- **A5.4 CHANGELOG** + versioning semantico, aggiornati a ogni traguardo.

---

# FASE B — Le feature differenzianti

*Ognuna: brainstorm → spec → piano → build → test, con branch e merge propri. L'ordine costruisce il valore in modo che ogni passo differenzi e che nulla vada rifatto.*

## Traguardo F1 — Consolidamento concetti

- **F1.1 Rilevazione quasi-doppioni.** Stesso concetto con nomi/lingue diverse (*Hybrid search* ≡ *Ricerca ibrida*, *Reranker/Reranking*, *RAG* duplicata). Segnali: alias, relazioni, sovrapposizione testuale, check LLM leggero.
- **F1.2 Fusione guidata.** Unisci in una scheda canonica accumulando provenienza, alias e relazioni (riusa `merge_notes`), con **coda di revisione** per i casi incerti.
- **F1.3 Riallineo indici.** Aggiorna ontologia/grafo/wikilink dopo la fusione: nessun link rotto.
- *Perché ora:* meno rumore, e **cluster/overview più puliti** per F2.

## Traguardo F2 — Overview gerarchico (tipizzato + temporal-aware)  *(il centro)*

*Risponde alla domanda chiave: dare all'LLM un quadro di **tutta** la memoria per scegliere da dove partire, senza far crescere i token con la grandezza della memoria. Soluzione: astrazione gerarchica (domini) → costo per domanda ~logaritmico, non lineare.*

- **F2.1 Induzione domini.** Raggruppa le schede in **domini** usando struttura del grafo + **ontologia tipizzata** (clustering guidato dai tipi di relazione, non solo statistico); l'LLM **nomina e descrive** ogni dominio a tempo di indicizzazione. **MVP: un livello.**
- **F2.2 Artefatti overview.** Genera/aggiorna `overview` (mappa dei domini, dimensione ~costante) e `index` (catalogo) a ogni reindex — ispirati a llm_wiki ma **tipizzati**.
- **F2.3 Motore di risposta unico.** `answer(domanda, storico=[])`. Pipeline: overview → l'LLM sceglie il dominio → drill-down sulle schede di quel dominio → sceglie l'ingresso → legge → **naviga via ontologia/wikilink** → risposta citata, con **budget di contesto**.
- **F2.4 Superfici sullo stesso motore.** `kortex ask`, MCP tool `overview`/`map`, e predisposizione per la **chat UI** (parametro `storico`). *Un solo motore, niente secondo cervello.*
- **F2.5 Embedding come adapter OPZIONALE** (via Ollama), **spento di default**: rete di sicurezza per l'ingresso quando la navigazione gerarchica sbaglia la prima svolta.
- **F2.6 Predisposizione temporale.** Domini e schede portano la **validità temporale** fin da subito, così F3 estende **senza rifacimenti**.
- **F2.7 Albero multi-livello** (oltre ~qualche migliaio di schede): split dei domini grossi in sotto-domini. *Dopo l'MVP, quando la scala lo richiede.*

## Traguardo F3 — Grafo bitemporale + invalidazione  *(il moat)*

- **F3.1 Modello bitemporale.** Ogni fatto/relazione porta **valid-time** (quando è vero nel mondo) e **transaction-time** (quando l'abbiamo saputo).
- **F3.2 Invalida-non-cancella.** Una contraddizione **chiude** il fatto vecchio (non più valido da T) invece di sovrascriverlo — l'opposto della loro cancellazione-a-cascata.
- **F3.3 Query temporali.** "Cosa era vero al tempo T?" / "mostrami com'è cambiata questa conoscenza".
- **F3.4 Le note non si spostano.** L'overlay ontologico/temporale è un **indice ricostruibile**; il Markdown resta la vista umana.
- **F3.5 Integrazione retrieval.** Di default si risponde con la verità **corrente**, ma le verità passate restano interrogabili e **citabili**.

## Traguardo F4 — Correzione-da-fonte (provenienza attiva)

- **F4.1 Rilevazione dubbio.** Durante un ask, se la risposta è poco confidente o c'è contraddizione, **segnala**.
- **F4.2 Verifica alla fonte.** Apri la fonte conservata (raw + normalizzata) e confronta col contenuto della scheda.
- **F4.3 Correzione tracciata.** Aggiorna la scheda registrando la correzione nel **modello bitemporale** (la versione vecchia resta come passato).
- **F4.4 Coda di revisione.** Le correzioni a bassa confidenza passano da Giovanni prima di entrare.

## Traguardo F5 — Sorgenti multi-formato

- **F5.1 Formati.** PDF (testo) + **OCR** immagini; poi DOCX/PPTX e web-clip (Readability). *Per recuperare terreno su llm_wiki sugli input.*
- **F5.2 Provenienza per-locator.** Pagina/sezione conservate nella provenance.
- **F5.3 Cache incrementale per hash.** Non ri-processare ciò che non è cambiato — ispirato a llm_wiki.

---

# FASE C — UI + visualizzazione

## Traguardo F6 — UI Kortex

- **F6.1 Chat-sulla-memoria** sullo **stesso** motore `answer(...)` (nessun secondo cervello).
- **F6.2 Effetto-Wikipedia:** lettura schede con **anteprima all'hover** dei wikilink.
- **F6.3 Navigazione per domini:** l'overview di F2 resa sfogliabile.
- **F6.4 Visualizzazione grafo** (ispirata alla loro sigma.js) — ma con relazioni **tipizzate** e **temporali**.
- **F6.5 Endpoint MCP remoto autenticato** (da `kortex-future-evolutions.md`) per gli LLM da browser: **sola lettura + auth**.

---

## Cross-cutting (a ogni traguardo)

- Test verdi e **CI verde sui tre OS**.
- `docs/`, README e CHANGELOG **aggiornati** insieme al codice (non dopo).
- Nessun wikilink/test rotto.
- Da **F1** in poi: ogni traguardo ha il suo **brainstorm → spec → piano** prima di scrivere codice.

## Fuori scope per ora

Vedi `kortex-future-evolutions.md` (endpoint remoto autenticato in dettaglio; graph-routing con set di valutazione; ecc.). Si tirano dentro quando il valore lo giustifica.
