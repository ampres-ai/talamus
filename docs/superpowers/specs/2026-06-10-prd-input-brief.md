# Talamus — Brief d'input per il PRD

**Scopo di questo documento.** È l'input per un modello che scriverà un **PRD** completo per la prossima fase di **Talamus**. Il PRD sarà poi eseguito da un modello ad alta capacità. Questo brief copre tre cose: (a) cosa è Talamus e dov'è ora, (b) cosa va **verificato** allo stato attuale, (c) cosa va **migliorato / portato al livello successivo / ripensato**, con enfasi speciale sull'**ontologia auto-emergente** come contributo di ricerca centrale.

> Il modello che scrive il PRD **non ha accesso al codice**: qui sotto c'è il contesto sufficiente. Sii concreto, onesto e misurabile; distingui sempre "da verificare" da "da costruire". Rispetta i vincoli in §5.

---

## 1. Il prodotto in una pagina

**Talamus** è un *knowledge compiler* **local-first** con **recupero graph-first**, pensato come **memoria unica**: secondo cervello dell'utente **e** memoria per agenti AI. Compila sorgenti (documenti, note, sessioni di lavoro di agenti) in **note-concetto atomiche, cross-linkate e ancorate alla fonte**, costruisce un **grafo tipizzato come indice** (non come verità), e risponde **con citazioni**, sull'engine LLM che l'utente già usa.

**Tre proprietà-moat, che insieme nessun altro dà:**
- **TIME** — grafo bitemporale: le contraddizioni *invalidano* i fatti vecchi invece di cancellarli (storico + "verità al tempo T").
- **MEANING** — **ontologia tipizzata auto-emergente** (uses / is-a / part-of / contrasts-with / depends-on) su cui l'LLM ragiona, non "pagine correlate".
- **VERIFIABILITY** — ogni nota conserva le **fonti** e l'originale è preservato: si può verificare e correggere contro la fonte.

**Cuneo di mercato:** memoria per **agenti** che hanno bisogno di verità corrente, citata, ragionata. Competitor di riferimento: `github.com/nashsu/llm_wiki` (virale; ottimo prodotto ma versioning assente, grafo statistico, provenance passiva).

**Principio guida ("il quid"):** l'**ontologia auto-emergente** è l'elemento differenziante e potenzialmente di ricerca. Vedi §4.3.

---

## 2. Stato attuale (baseline su cui costruire)

**Storage ibrido:** `notes/*.md` = vista umana editabile (Obsidian-compatibile, `id` stabile in frontmatter); `.talamus/cache/notes/<id>.json` = verità macchina (provenienza, relazioni, retrieval_text, confidence); indici derivati ricostruibili = `graph.json`, `bm25.json`, `ontology.json`, `overview.json`, `manifest.json`; storico bitemporale in `.talamus/cache/history/<id>.jsonl`; cache incrementale per hash in `ingested.json`. **Il grafo è un indice, non la verità.**

**Pipeline:** sorgente → normalizzazione (originale preservato) → estrazione LLM in note-concetto (skeleton Definizione/Funzionamento/Quando/Esempio/Relazioni, con fonti + relazioni tipizzate + wikilink) → indici (grafo + BM25 + ontologia) + **overview gerarchico dei domini**.

**Recupero:** overview-routed (l'LLM sceglie i domini pertinenti dalla mappa → legge quelle note) con fallback; poi **rerank** deterministico dell'unione grafo+BM25 con boost sul titolo esatto (confine-di-parola); il contesto è **cappato a budget di token** (costo risposta ~piatto al crescere del brain). Tokenizer con **stemmer leggero italiano**.

**Ontologia/overview (stato reale):** le **relazioni tipizzate** sono assegnate dall'LLM in fase di estrazione da un **insieme fisso e piccolo** di tipi. `ontology.py` fa normalizzazione delle relazioni, unificazione dei concetti via registro delle note, e `neighbors`. I **domini** (overview) sono indotti in modo **ibrido**: cluster strutturali via union-find sui vicini tipizzati + **naming/assegnazione fatti dall'LLM**. Costo ~log(N) token (dichiarato, **da verificare**).

**Bitemporale:** MVP solo *transaction-time* — `talamus history [--as-of]`, invalidate-not-delete via history jsonl. *Valid-time* non modellato.

**Verificabilità:** `talamus verify [--apply]` confronta una nota con la fonte preservata e corregge (vecchia versione → storico).

**Superfici:** **CLI** ricca (`init/demo/ui/status/doctor/reindex/ingest/consolidate/verify/ask/overview/search/read/history/recall/neighbors/relations/remember/eval/quickstart/brains/where/export/import/completion/mcp/hook/hook-run`, `--version`); **SDK** Python; **MCP** read+write (`search/read_note/recall/overview/neighbors/remember`) per agenti; **UI Flet** desktop/web (chat, cerca, vista nota con wikilink cliccabili, domini) che chiama l'SDK diretto (no API).

**Ingestion:** file/cartella(ricorsiva, incrementale)/URL; formati Markdown/testo, **PDF** (extra `pdf`), **DOCX** e **HTML** (stdlib). L'ingest di cartelle riporta i file falliti. `read_url` con User-Agent.

**Qualità:** core **Python stdlib-only**, extra opzionali (`mcp/pdf/ui/docling/bench/docs/dev`); gate `ruff + mypy + unittest` (~154 test verdi), CI multi-OS, `talamus eval` (recall@k/precision@k/MRR) con harness intercambiabile.

---

## 3. DA VERIFICARE allo stato attuale (validare prima di costruire sopra)

Sono affermazioni/assunzioni **non ancora misurate o note-deboli**. Il PRD deve prevedere come verificarle.

- **Qualità del recupero su corpus reale.** L'harness `eval` esiste ma il set di valutazione è **sintetico**. Serve un **eval-set reale** (domande↔note attese) e numeri recall@k/MRR su un brain vero, incluse **domande vaghe / non tecniche** (obiettivo dichiarato).
- **Costo dell'overview a scala.** Verificare che il costo-token dell'overview-routing sia davvero ~log(N) a 100 / 1.000 / 10.000 note, e che il routing resti preciso.
- **Qualità dell'ontologia auto-emergente.** Nessuna metrica: i tipi/domini indotti sono **coerenti, stabili, utili**? (vedi §4.3 per le metriche).
- **Qualità dell'estrazione.** Le note sono atomiche e fedeli alla fonte? Spot-check + un protocollo di valutazione.
- **Scala / latenza.** `query_graph`, BM25 e `search_notes` fanno scansioni **O(N) per query** (niente indice invertito persistito). Misurare latenza/costo a 10³–10⁵ note e identificare il muro.
- **Economicità complessiva** (preoccupazione #1): contare le chiamate LLM per ingest/overview/ask e il costo totale; verificare che sia **decorrelato dalla dimensione** del brain.
- **Bitemporale.** Semantica di `--as-of` (confronto stringhe ISO; **edge** con timestamp solo-data); manca valid-time.
- **Multi-brain.** 🐞 `talamus init` senza `--root` passa per lo scoping e inizializza il **globale** invece della cartella corrente (il pannello/quickstart promettono "init crea qui"): **bug da correggere**. Nessun registro dei brain di progetto, nessun cross-brain.
- **Routing overview** (`ask.py`): selezione dei domini per **sottostringa** sul testo dell'LLM (es. "AI" ⊂ "AI Safety"): possibile falso match, **non misurato**.
- **Consolidamento e correzione-da-fonte** su dati reali e a scala (entrambi LLM-dipendenti, non testati oltre l'MVP).
- **UI runtime:** type-checked contro Flet ma la resa/uX va verificata eseguendo `talamus ui`.

---

## 4. DA MIGLIORARE / LIVELLO SUCCESSIVO / RIPENSARE

### 4.1 Multi-brain: centrale + per-progetto (decisione architetturale aperta)
Oggi: "casa globale" `TALAMUS_HOME` con brain con nome; brain di progetto = cartella con `talamus.json` trovata risalendo; precedenza `--root > --brain > --global > progetto > default`. Mancano: un "centrale" vero, ricerca cross-brain, registro dei brain di progetto, `use`/switch, `info`/`rename`/`delete`, e il fix del bug di `init`.
**Domanda aperta da risolvere nel PRD — relazione centrale↔progetto, scegliere il modello:**
- **(A) Gerarchia stile git:** il progetto aumenta il centrale; query = progetto poi centrale (fallback); `remember`/`ingest` scrivono nel progetto, con "promozione" esplicita al centrale.
- **(B) Centrale federato:** il centrale interroga in lettura tutti i brain di progetto registrati; richiede federazione/indice cross-brain.
- **(C) Isole gestite bene:** brain indipendenti + ottimo tooling (registro, lista-tutti, switch, info, rename/delete).
Definire anche: registro globale dei brain, comando `use`, policy di scrittura, e la **migrazione** del modello di scoping.

### 4.2 Auto-estrazione su `init` (repo esistente) — la feature richiesta
Quando si inizializza un brain in una cartella di progetto, deve **partire un'estrazione di note su tutta la repository già presente**. Da progettare con cura:
- **Scope dei file:** quali includere? Solo testo/doc (md/rst/txt) o anche **codice**? Rispettare `.gitignore`? Set di include/exclude configurabile; saltare `node_modules`/binari/`.git`/lockfile.
- **Codice vs prosa:** l'estrattore attuale è tarato sulla prosa. Per il codice serve un trattamento diverso (riassunti di modulo, architettura, API pubbliche, dipendenze) — oppure v1 limitata ai file-testo con il codice rimandato.
- **Costo/scala:** una repo grande = molte chiamate LLM. Prevedere **dry-run / anteprima** (conta file e stima costo), **conferma**, limiti, **batching**, incrementale, esecuzione **in background**, ripresa.
- **UX:** `talamus init --scan` o prompt? Default sicuro (non far partire un'estrazione costosa a sorpresa). Report finale (note create, file saltati e perché).
- **Provenienza:** locator per file/sezione; collegare le note al commit/stato del repo (utile col bitemporale).

### 4.3 ⭐ Ontologia auto-emergente — la frontiera di ricerca (sezione centrale)
**Stato reale (onesto):** i **tipi di relazione** provengono da un **insieme fisso** dato all'LLM in fase di estrazione; i **domini** sono cluster strutturali (union-find) **nominati dall'LLM**. Quindi oggi è "auto-emergente" a metà: emergono i *cluster* e i *nomi*, ma **non il sistema di tipi**, che è prescritto.
**Salto di livello (dove il modello potente può fare vera ricerca):**
- **Induzione non supervisionata del sistema di tipi:** far **emergere** i tipi di relazione e le categorie dal corpus invece di prescriverli (ontology learning / unsupervised relation & schema induction / taxonomy induction). Obiettivo: un'ontologia che si auto-organizza e si **evolve** col crescere e cambiare della conoscenza.
- **Ontologia bitemporale:** i tipi/relazioni cambiano nel tempo; integrare l'ontologia col grafo bitemporale (concetti che si fondono/scindono, tipi che nascono/deprecano), versionando lo *schema* stesso.
- **Stabilità vs plasticità:** come far evolvere l'ontologia senza farla "sbandare" a ogni ingest (concept drift, ancoraggio, soglie, revisione umana in coda).
- **Metriche di qualità dell'ontologia** (oggi assenti): coerenza dei cluster, stabilità tra run/ingest, copertura, utilità per il recupero (l'ontologia migliora recall@k/MRR rispetto al baseline?), accordo con giudizio umano.
- **Uso dell'ontologia nel recupero e nel ragionamento:** routing, espansione, spiegazioni; rendere l'ontologia un cittadino di prima classe del recupero (oggi il graph-routing aggressivo è stato trovato fragile e va ripensato con un eval-set).
- **Domande scientifiche aperte da inquadrare nel PRD:** quale segnale (co-occorrenza tipizzata, embedding, struttura del grafo, prompting strutturato, programmi LLM) induce tipi stabili e significativi senza supervisione? Come valutarli? Come renderli **economici a scala**? Qual è il contributo nuovo rispetto alla letteratura (KG construction, OpenIE, ontology learning, GraphRAG, Zep/temporal KG)?

### 4.4 Recupero economico a scala (il moat "cheap at scale")
Indici **invertiti persistiti** (posting list) per evitare scansioni O(N); overview **multi-livello/gerarchico**; rerank pesato/learned; **eval-set reale** + harness in CI; budget/quote multi-sezione (wiki/chat/index/sistema); cache dei risultati.

### 4.5 Bitemporale completo
Aggiungere **valid-time** oltre al transaction-time; invalidazione delle contraddizioni in stile temporal-KG come **overlay** (le note non si spostano mai); query "as-of" robuste (date parziali, timezone).

### 4.6 Verificabilità attiva
Provenance attiva (ri-verifica periodica vs fonte), correzione-da-fonte a scala, propagazione della confidence, segnalazione note "stantie".

### 4.7 Interfacce & packaging
UI oltre l'MVP: anteprima-hover dei wikilink (effetto-Wikipedia), **viz del grafo**, **ingest da UI** (file/cartelle/URL), **code di revisione** (consolidamento/correzione/proposte d'ontologia con approvazione), storia bitemporale + editing note; **installabili nativi** (`flet build`); endpoint MCP remoto autenticato per LLM web.

### 4.8 Ampiezza ingestion
OCR (PDF scansionati/immagini), PPTX/XLSX/EPUB, repo di codice (vedi 4.2), media (vision/audio/video), RSS/auto-watch, chat/email, locator pagina/sezione, coda resiliente.

### 4.9 Agent-memory / MCP
Policy di scrittura (cosa "vale la pena ricordare"), **promozione progetto→centrale**, qualità della cattura di sessione, strumenti MCP per overview/history, endpoint remoto.

---

## 5. Vincoli e non-negoziabili (il PRD deve rispettarli)
- **Core Python stdlib-only**; tutto il resto come **extra opzionali**. Niente dipendenze pesanti nel core.
- **Local-first**: nessun cloud obbligatorio; i dati restano sulla macchina.
- **LLM-provider-agnostico**: `claude-cli` / `ollama` / `anthropic-api` selezionabili da config/env; non legare il design a un fornitore.
- **Storage ibrido invariante**: `notes/*.md` verità umana, cache = verità macchina, **grafo = indice non verità**; le note **non si spostano mai** (bitemporale come overlay).
- **Provenienza sempre**: ogni affermazione tracciabile alla fonte; originali preservati.
- **Qualità**: ruff + mypy + unittest verdi, CI multi-OS; **cross-platform con realtà Windows-first**.
- **Economicità**: il costo (token/latenza) deve **decorrelarsi dalla dimensione** del brain.
- **CLI/SDK/MCP/UI** restano sottili sopra un core testato (la UI non duplica logica).

## 6. Criteri di successo ("livello successivo" misurabile)
- Recupero **preciso anche su domande vaghe/non tecniche** (numeri su eval-set reale).
- Costo di accesso **piatto** a 10³–10⁵ note (token e latenza misurati).
- **Ontologia auto-emergente** con metriche di qualità/stabilità che battono il baseline a tipi-fissi.
- `init` su una repo esistente → brain utile **in pochi minuti**, costo prevedibile.
- Multi-brain con modello chiaro centrale↔progetto e tooling completo.
- Vantaggio difendibile vs `llm_wiki` su **TIME / MEANING / VERIFIABILITY**.

## 7. Domande aperte che il PRD deve chiudere
1. Modello multi-brain: A / B / C (§4.1) + migrazione dello scoping.
2. Scope e UX dell'auto-estrazione su init (file inclusi, codice sì/no, costo/conferma) (§4.2).
3. Approccio all'induzione **non supervisionata** del sistema di tipi e metriche di qualità dell'ontologia (§4.3).
4. Strategia di indicizzazione per la scala (indici invertiti, overview multi-livello) (§4.4).
5. Modello bitemporale completo (valid-time + invalidazione overlay) (§4.5).
6. Confini di ciò che è "da verificare adesso" vs "da costruire" (§3).

## 8. Puntatori
- **Repo:** `github.com/GCrapuzzi/Talamus-Wiki` (CLI `talamus`, pacchetto `talamus`).
- **Roadmap viva (bibbia di sviluppo):** `docs/superpowers/specs/2026-06-08-talamus-roadmap.md` (fasi A foundations, B differenzianti, C sorgenti, D interfacce, E scala/ops, con stati ✅/🟡/⏳).
- **Design UI:** `docs/superpowers/specs/2026-06-08-talamus-ui-design.md`.
- **Competitor:** `github.com/nashsu/llm_wiki`.
- **Moduli chiave:** `store.py`, `models.py`, `extract.py`, `ingest.py`, `sources.py`, `graph.py`, `search.py`, `rank.py`, `budget.py`, `ask.py`, `recall.py`, `domains.py`, `ontology.py`, `timeline.py`, `correct.py`, `consolidate.py`, `eval.py`, `cli.py`, `mcp_server.py`, `ui/app.py`.

---

### Istruzioni finali per il modello che scrive il PRD
Produci un PRD con: **problema & obiettivi/non-obiettivi**, **user stories**, **requisiti funzionali e non-funzionali**, una **sezione di ricerca dedicata all'ontologia auto-emergente** (ipotesi, metodo, esperimenti, metriche, criteri di successo), **milestone incrementali** ciascuna spedibile e gate-verde, **rischi & mitigazioni**, **criteri di accettazione misurabili**, e una mappa esplicita di **"da verificare" vs "da costruire"**. Mantieni l'ontologia auto-emergente come filo centrale. Rispetta i vincoli §5. Sii critico e onesto: dove l'attuale è debole o non misurato, dillo.
