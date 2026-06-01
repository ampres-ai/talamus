# Kortex — Fondamenta Architetturali (la spina dorsale)

Data: 2026-05-29
Stato: bozza per revisione. Contratto stabile.

## Scopo e regola

Questo documento fissa **solo** le decisioni costose da cambiare dopo: il modello
dati, il formato-verità su disco, i giunti tra i componenti e la forma dell'API
pubblica. Tutto il resto (strategia di estrazione, ontologia avanzata, convertitori
PDF/OCR) è volutamente lasciato alle note di design **per-traguardo**.

Regola: i **giunti** qui definiti sono stabili; gli **interni** dietro ogni giunto
possono essere riscritti senza toccare il resto. È ciò che ci permette i mini-pivot
senza demolire tutto.

Riferimento: [visione di prodotto](2026-05-29-kortex-product-vision.md).

## 1. Mappa dei moduli

Il motore senza UI, i bordi che lo espongono, lo store che tiene la verità.

- **`kortex.model`** — tipi dati canonici. Solo dati, nessun I/O.
- **`kortex.store`** — l'**unico** a toccare il disco per la conoscenza: legge/scrive
  la verità (Markdown) e la cache derivata (`.kortex/`).
- **`kortex.adapters`** — i **giunti** (interfacce): converter, llm, search, ontology,
  renderer.
- **`kortex.engine`** — orchestrazione: ingest, extract, link, render, index,
  retrieve. Usa adapters + store.
- **`kortex.api`** (SDK) — le funzioni pubbliche. L'**unica vera API**.
- **bordi**: **`kortex.cli`** e **`kortex.mcp`** — involucri sottili sopra l'SDK.

Dipendenze a senso unico:
`bordi → api → engine → (adapters, store) → model`. Mai al contrario.

## 2. Modello dati canonico

Entità: **Scheda** (Note), **Fonte** (Source), **Concetto**, **Categoria**,
**Dominio**, **Relazione**, **Link**.

- **Scheda**: id stabile · titolo · alias · categoria/dominio · tag · riassunto ·
  `retrieval_text` · sezioni del corpo · link · relazioni · fonti · confidenza ·
  date (created/updated).
- **Fonte (provenienza)**: percorso grezzo · percorso normalizzato · locator (es.
  "pagine 42-48") · hash · affermazioni supportate.
- **Relazione**: sorgente · tipo · bersaglio · confidenza · **campi temporali**
  (valido_da / valido_a, registrato_da / registrato_a).
- **Concetto / Categoria / Dominio**: entità di prima classe.

Decisioni-chiave (costose da aggiungere dopo, gratis da portare ora):
- l'**ontologia vive nel modello dal giorno 1** (concetti/categorie/domini/relazioni
  tipizzate esistono come dati), anche se il motore che la popola cresce nel tempo;
- ogni relazione/fatto **porta i campi temporali fin da subito**, anche se la logica
  bi-temporale (invalidazione, interrogazioni nel tempo) arriva al Traguardo 3.

## 3. Formato e verità su disco (deciso 2026-05-29, rivisto nel Traguardo 1)

> Revisione onesta: nella visione iniziale il Markdown era l'"unica verità". In fase
> di costruzione abbiamo scelto un **modello ibrido**, più pragmatico (scelta di
> Giovanni). Questa sezione descrive il modello effettivo, non quello iniziale.

- **Due rappresentazioni, due ruoli:**
  - **Markdown in `notes/`** = la **vista umana**: in chiaro, leggibile e modificabile
    a mano (anche da Obsidian). È ciò che editi. Porta un `id` stabile nel frontmatter.
  - **Oggetto canonico in `.kortex/cache/notes/<id>.json`** = la **verità "macchina"**:
    tiene i campi che l'umano non scrive a mano (provenienza/fonti, relazioni,
    `retrieval_text`, confidenza).
- **Riconciliazione esplicita con `kortex reindex`:** rilegge i `.md` e aggiorna la
  cache prendendo dai file i **campi umani** (titolo, alias, tag, riassunto, sezioni)
  e **preservando i campi macchina** dalla cache. Così le modifiche a mano contano,
  senza perdere la provenienza. L'aggancio nota↔oggetto è l'`id` nel frontmatter.
- **Indici derivati** (grafo e ricerca: oggi file `graph.json` e `bm25.json` in
  `.kortex/cache/`; in futuro eventualmente SQLite/ontologia) sono **ricostruibili**
  da `reindex`/ingest.
- **Trade-off accettato:** se cancelli `.kortex/` perdi la provenienza (recuperabile
  ri-ingerendo le fonti). Il Markdown da solo non ricostruisce i campi macchina —
  è il prezzo della semplicità (niente parser YAML completo per ora).
- **Layout di un "brain":** `notes/` in chiaro + `.kortex/` (grezzo, normalizzato,
  cache, log). **Un brain = una cartella** autocontenuta; esistono un brain
  **globale** e brain **per-progetto** (che può leggere dal globale).
- **Git**: commit ai checkpoint; il grezzo non viene mai distrutto.

> Evoluzione futura possibile: se servisse il "Markdown come unica verità" pieno
> (ricostruire tutto dai soli `.md`), si aggiungerebbe un frontmatter completo + un
> parser dedicato. Fuori dal traguardo attuale.

## 4. Giunti degli adattatori (le interfacce che abilitano i pivot)

Ogni capacità strategica sta dietro un'interfaccia stabile; gli interni si
sostituiscono liberamente.

- **Converter**: grezzo → pacchetto normalizzato (sezioni + provenienza).
  Impl: testo/sessione (T1) · PDF · OCR (T2).
- **LLMProvider**: i 3 modi (CLI-abbonamento / API-chiave / locale), default
  **auto-rilevato** al primo avvio.
- **SearchIndex**: ricerca lessicale di riserva. Impl: BM25 integrato (già esiste).
- **Ontology/Graph**: costruzione, interrogazione, vicini, aggiornamento.
  Impl: minima (T1) → bi-temporale (T3).
- **Renderer**: scheda canonica → Markdown (sapore Obsidian o piano).

Ora è fissata **solo la forma** dei giunti, non gli interni.

## 5. Superficie pubblica (l'SDK è l'unica vera API; CLI e MCP la avvolgono)

Verbi stabili dell'SDK:
`init` · `ingest` · `remember` (deposita una sessione) · `ask` · `search` ·
`graph_neighbors` · `read_note` · `read_source` · `review` (lista/approva/scarta) ·
`forget`.

- **`ask` a doppia modalità**: interrogazione diretta → **risposta confezionata e
  citata**; dentro un agente → **solo le risorse** (risponde l'LLM dell'agente).
- **CLI** = mappatura di questi verbi su `kortex ...`.
- **MCP** = mappatura su strumenti agente (cerca · naviga la mappa · leggi
  scheda/fonte · deposita).

Aggiungere verbi è lecito; cambiarne la semantica no.

## 6. Invarianti trasversali (vincolano ogni modulo)

- verità ibrida: Markdown = vista umana, JSON in `.kortex/` = verità macchina,
  `reindex` riconcilia; indici derivati ricostruibili; grezzo mai perso;
- provenienza obbligatoria; grafo/ontologia = indice, **non** verità;
- local-first; **leggero** (lavoro pesante differito e incrementale, mai bloccante);
- revisione **non bloccante**; git automatico ai checkpoint; **zero telemetria**.

## Cosa NON è qui (di proposito)

La strategia di **estrazione**, gli **algoritmi dell'ontologia** (specie il modello
bi-temporale) e i **convertitori PDF/OCR**. Vivono nelle note di design
**per-traguardo**, scritte appena prima di costruirli — così restano morbidi e
pivotabili. La spina qui sopra li protegge.
