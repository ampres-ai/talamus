# Talamus Final Product PRD

**Data:** 2026-06-10
**Stato:** PRD operativo per la fase finale di prodotto.
**Input primario:** `docs/superpowers/specs/2026-06-10-prd-input-brief.md`
**Documenti vincolanti letti:**
- `docs/superpowers/specs/2026-05-27-local-first-knowledge-pipeline-v1-design.md`
- `docs/superpowers/specs/2026-05-28-talamus-repository-cleanup-design.md`
- `docs/superpowers/plans/2026-05-28-talamus-repository-cleanup.md`
- `docs/superpowers/specs/2026-06-08-talamus-roadmap.md`
- `docs/superpowers/specs/2026-06-08-talamus-ui-design.md`

## 1. Executive Summary

Talamus deve diventare il knowledge compiler local-first definitivo per umani e
agenti AI: prende sorgenti reali, le preserva, le normalizza, le compila in note
concetto atomiche e verificabili, costruisce un grafo tipizzato come indice, e
risponde leggendo note Markdown reali con citazioni.

La fase finale non deve limitarsi a "completare feature". Deve trasformare gli
MVP attuali in un prodotto affidabile, misurato e difendibile su tre moat:

1. **TIME:** verita' corrente e verita' storica interrogabili senza cancellare il
   passato.
2. **MEANING:** ontologia emergente, evolutiva e misurata, non un insieme fisso
   di relazioni cosmetiche.
3. **VERIFIABILITY:** ogni risposta e ogni nota riconducono a sorgenti reali,
   preservate e ricontrollabili.

Il risultato finale deve essere un prodotto installabile, bello da usare in CLI
e UI, solido per agenti tramite MCP, economico a scala, e scientificamente serio
nella sua parte piu' ambiziosa: l'induzione dell'ontologia.

## 2. Baseline Reale

Questa baseline deriva dal brief e da lettura del repository in data
2026-06-10.

### 2.1 Esiste Gia'

- Package Python `src/talamus/`, CLI `talamus`, config `talamus.json`.
- Core stdlib-only con extra opzionali `mcp`, `ui`, `pdf`, `docling`, `bench`,
  `docs`, `dev`.
- Storage ibrido:
  - `notes/*.md` come vista umana editabile.
  - `.talamus/cache/notes/<id>.json` come verita' macchina.
  - `.talamus/raw/` e `.talamus/normalized/` per sorgenti preservate.
  - `graph.json`, `bm25.json`, `ontology.json`, `overview.json`,
    `manifest.json` come indici derivati.
- Pipeline di ingest file/cartelle/URL:
  - Markdown, testo, RST, PDF via extra, DOCX stdlib, HTML stdlib, URL con
    User-Agent.
  - Cache incrementale per hash.
  - Errori per file falliti in import cartella.
- Estrazione LLM in `CanonicalNote` con fonti, relazioni, wikilink,
  `retrieval_text`, confidence.
- Grafo deterministico da note canoniche.
- BM25 built-in serializzato in JSON.
- Reranking deterministico graph + BM25 + boost titolo/alias esatto.
- Budget token sul contesto di risposta.
- Overview a domini indotta in modo ibrido:
  - cluster strutturali da vicini tipizzati.
  - naming e assegnazione via LLM.
- `ask` con routing su overview e fallback graph/BM25.
- `eval` con recall@k, precision@k, MRR, hit-rate su casi JSON.
- Bitemporale MVP transaction-time:
  - versioni precedenti in `.talamus/cache/history/<id>.jsonl`.
  - `talamus history [--as-of]`.
- Verifica da fonte MVP:
  - `talamus verify [--apply]`.
- Consolidamento concetti:
  - `talamus consolidate [--apply]`.
- Ontologia MVP:
  - tipi fissi `uses`, `is-a`, `part-of`, `contrasts-with`, `depends-on`,
    `related`.
  - `talamus relations [--prune]`.
- CLI ampia.
- SDK interno usato da CLI, MCP e UI.
- MCP read+write.
- UI Flet sottile con Chat, Cerca, Domini, Vista nota con wikilink cliccabili.
- Documentazione utente e roadmap.

### 2.2 Debolezze Reali Da Non Nascondere

- `talamus init` senza `--root`, se non trova `talamus.json` risolve il brain
  globale default invece della cartella corrente. Questo contraddice quickstart
  e aspettativa "inizializza qui".
- L'ontologia non e' ancora auto-emergente in senso pieno: i tipi di relazione
  sono prescritti dal codice/prompt, mentre emergono soprattutto cluster e nomi.
- `query_graph_scored`, `BM25Index.search` e parti di `search_notes` scandiscono
  tutti i nodi/documenti per query.
- L'overview routing in `ask.py` riconosce domini con match di sottostringa sul
  testo restituito dall'LLM; puo' confondere nomi come `AI` e `AI Safety`.
- L'eval harness esiste, ma serve un eval-set reale.
- Il costo-token reale di ingest, overview, ask e verify non e' misurato in modo
  sistematico.
- Il bitemporale e' transaction-time, non valid-time.
- `--as-of` confronta stringhe ISO e non ha parsing robusto di date parziali,
  timezone, date-only, intervalli validi.
- La UI e' type-checked ma non ancora verificata come esperienza runtime
  definitiva.
- Non esiste coda persistente per job lunghi, review, proposte ontologiche,
  correzioni, scan repo o ingest a scala.
- Il multi-brain e' parziale: global/project scoping esiste, ma mancano registro
  completo, `use`, `info`, `rename`, `delete`, promozione project-to-central,
  indice federato locale, query su tutti i brain registrati e policy di
  scrittura.

## 3. Problema

Gli utenti e gli agenti accumulano conoscenza in sorgenti sparse: note,
documenti, repository, sessioni di lavoro, chat, pagine web e file locali. Gli
strumenti correnti risolvono solo parti del problema:

- RAG tradizionale: recupera chunk, ma non produce memoria umana, non conserva
  bene provenienza e non ragiona su relazioni tipizzate.
- Wiki personali: sono leggibili, ma non compilano automaticamente sorgenti in
  conoscenza verificabile e interrogabile dagli agenti.
- GraphRAG/knowledge graph: spesso sono cloud-first, fragili da mantenere,
  costosi, o trattano il grafo come verita' invece che come indice.
- Memorie agentiche: catturano eventi, ma spesso non hanno verita' temporale,
  verificabilita' da fonte e controllo umano.

Talamus deve risolvere il problema in modo locale, economico, verificabile e
usabile:

> Trasformare fonti reali in una memoria viva che umani e agenti possono leggere,
> correggere, interrogare e far evolvere senza perdere storia, contesto e prove.

## 4. Visione Di Prodotto

Talamus e' una "compiler toolchain" per conoscenza personale e agentica.

Il flusso definitivo:

```text
sorgenti reali
  -> preservazione raw
  -> normalizzazione con locator
  -> estrazione strutturata
  -> note Markdown editabili
  -> cache macchina con provenance
  -> indici derivati graph/BM25/ontology/overview
  -> retrieval economico
  -> risposta citata o azione agente
  -> verifica/correzione/review
  -> storia temporale senza cancellazione
```

La CLI deve sembrare un prodotto maturo come Claude Code o Codex: comandi
chiari, stato leggibile, progressi affidabili, output machine-readable,
messaggi di errore azionabili, UTF-8 corretto e nessuna magia costosa non
richiesta.

La UI deve essere una workbench locale definitiva: chat citata, ricerca, wiki,
domini, grafo, timeline, ingest, review e ontologia in un'unica esperienza
coerente.

L'ontologia deve passare da MVP tipizzato a sistema di ricerca applicata:
emergente, versionato, valutato, utile al retrieval e comprensibile all'utente.

## 5. Obiettivi

### 5.1 Obiettivi Di Prodotto

1. Rendere `talamus init` e lo scoping multi-brain corretti, prevedibili e
   piacevoli.
2. Rendere una repository esistente utile in pochi minuti tramite scan sicuro,
   stimato, resumable e confermato.
3. Rendere retrieval e ask economici a scala, con costo decorrelato dalla
   dimensione del brain.
4. Rendere l'ontologia auto-emergente una feature misurata e difendibile.
5. Rendere bitemporalita' e verificabilita' parte del loop quotidiano, non solo
   comandi specialistici.
6. Rendere CLI e UI superfici complete ma sottili sopra lo stesso SDK.
7. Rendere Talamus una memoria agentica affidabile via MCP, con policy di
   scrittura, review e promozione.
8. Rendere il progetto release-ready: test, CI, docs, packaging, migrazioni,
   benchmark e safety Windows-first.

### 5.2 Obiettivi Scientifici

1. Progettare e implementare un percorso di ontology learning locale-first.
2. Misurare se l'ontologia emergente migliora retrieval e ragionamento rispetto
   al baseline a tipi fissi.
3. Versionare lo schema ontologico stesso nel tempo.
4. Governare stabilita' vs plasticita' con metriche, soglie e review umana.
5. Produrre un documento di ricerca interno che confronti Talamus con ontology
   learning, OpenIE, KG construction, GraphRAG e temporal knowledge graphs.

### 5.3 Obiettivi Di Qualita'

1. `python dev.py` verde.
2. `ruff`, `mypy`, `unittest` verdi sui 3 OS in CI.
3. Core runtime senza dipendenze obbligatorie oltre stdlib.
4. Nessun comando lungo senza progress, resume o log.
5. Nessuna risposta senza citazioni quando il contesto contiene fonti.
6. Nessun indice trattato come fonte di verita'.
7. Nessuna feature "finale" senza test o eval.

## 6. Non-Obiettivi

- Non costruire un SaaS obbligatorio.
- Non rendere cloud obbligatorio per ingest, retrieval, UI o agent memory.
- Non sostituire le note Markdown con un database opaco.
- Non rendere il grafo fonte di verita'.
- Non introdurre dipendenze pesanti nel core.
- Non vincolare il prodotto a un provider LLM specifico.
- Non fare scan costosi o chiamate LLM massive senza dry-run, stima e consenso.
- Non implementare federazione team/multiutente cloud in questa fase; la
  federazione richiesta qui e' locale, personale e basata su brain registrati
  sul filesystem dell'utente.
- Non promettere conversione perfetta di ogni PDF, immagine o media.
- Non ottimizzare per benchmark sintetici a scapito di citazioni e provenienza.

## 7. Utenti E Jobs To Be Done

### 7.1 Giovanni / Power User Locale

Vuole inizializzare una repository, compilare documenti e sessioni agentiche,
chiedere al brain, verificare risposte, e avere una UI che renda il sistema
usabile ogni giorno.

**Job:** "Quando entro in un progetto, voglio che Talamus capisca la repo,
costruisca una memoria del progetto e mi risponda con prove senza farmi pagare
token inutili."

### 7.2 Ricercatore / Knowledge Worker

Accumula PDF, note, pagine web e appunti. Ha bisogno di recuperare concetti,
contraddizioni, evoluzioni e fonti.

**Job:** "Voglio trasformare letture e note in una mappa viva che posso
interrogare, correggere e citare."

### 7.3 Agente AI

Ha bisogno di memoria persistente, citata e aggiornata, ma non deve scrivere
rumore o fidarsi di chunk non verificati.

**Job:** "Voglio richiamare contesto reale, leggere note e salvare solo
conoscenza utile, con provenance e scope corretto."

### 7.4 Contributor Open Source

Vuole capire il sistema, eseguire test e aggiungere adapter senza rompere core,
storage o retrieval.

**Job:** "Voglio un'architettura modulare, testata e documentata, con confini
chiari."

### 7.5 User Stories

US1. Come utente in una repository esistente, voglio eseguire `talamus init`
nella cartella corrente e ottenere un brain locale senza scrivere per errore nel
brain globale.

US2. Come utente in una repository esistente, voglio vedere un dry-run dello scan
con file inclusi, file esclusi, costo stimato e rischi privacy prima di avviare
chiamate LLM.

US3. Come utente, voglio chiedere "perche abbiamo scelto questa architettura?"
e ricevere una risposta citata da note reali e sorgenti preservate, non da
metadata del grafo.

US4. Come utente, voglio fare una domanda vaga e ottenere comunque le note
pertinenti tramite overview, ontologia e reranking misurati da eval-set reale.

US5. Come utente, voglio sapere cosa era vero a una certa data e vedere anche
quando Talamus ha registrato o invalidato quella conoscenza.

US6. Come utente, voglio verificare una nota contro la fonte e applicare una
correzione preservando la versione precedente.

US7. Come utente, voglio vedere proposte di ontologia con esempi, fonti,
confidence e impatto sui metriche prima di promuoverle nello schema attivo.

US8. Come agente AI, voglio richiamare contesto dal brain di progetto, dal
centrale o da tutti i brain registrati con scope esplicito, leggere note reali e
salvare solo memoria utile.

US9. Come agente AI, voglio scrivere una memoria incerta in review invece di
inquinare direttamente le note canoniche.

US10. Come utente della UI, voglio passare da chat a nota, fonte, grafo,
timeline e review senza perdere il contesto della domanda.

US11. Come contributor, voglio aggiungere un adapter di sorgente senza importare
dipendenze opzionali nel core e con test su locator, quality report e failure
reason.

US12. Come maintainer, voglio sapere da benchmark e CI se un cambiamento ha
peggiorato retrieval, costo, temporalita', ontologia o UX CLI.

## 8. Principi Non Negoziabili

1. **Local-first:** i dati restano locali salvo opt-in esplicito.
2. **Provider-agnostic:** Claude CLI, Ollama, Anthropic API e futuri provider
   sono adapter.
3. **Stdlib core:** extras opzionali per UI, MCP, PDF, docling, bench, docs.
4. **Storage ibrido invariato:** Markdown umano, JSON macchina, indici
   ricostruibili.
5. **Grafo come indice:** mai fonte di verita'.
6. **Provenienza sempre:** ogni claim importante punta a fonte e locator.
7. **Note non si spostano:** temporalita', invalidazioni e ontologia evolutiva
   vivono in overlay/cache/versioni.
8. **Windows-first reale:** path, encoding, console e file locking devono essere
   verificati su Windows.
9. **Costo esplicito:** ogni chiamata LLM deve essere contata o stimata.
10. **UI/CLI/MCP sottili:** logica nel core SDK testato.

## 9. Decisioni Architetturali Chiuse

### 9.1 Multi-Brain

**Decisione:** adottare un modello ibrido "Federated Hub with Project-Local
Ownership".

Il brain centrale personale ha due ruoli:

1. contiene conoscenza durevole e personale dell'utente;
2. funziona da hub federato in lettura sui brain di progetto registrati.

I brain di progetto restano locali, indipendenti e proprietari dei propri dati.
Il centrale puo' cercare ovunque, ma non assorbe automaticamente le note dei
progetti. La federazione cross-brain legge indici e metadata registrati e
restituisce pointer a `brain_id + note_id + path`. La source truth resta sempre
nel brain proprietario.

Dentro un progetto, il default resta prudente: query sul progetto corrente piu'
centrale personale. La ricerca su tutti i progetti registrati e' esplicita con
`--scope all` o `--all-brains`, oppure e' il default solo quando l'utente apre la
vista centrale/globale.

Scritture e ingest, per default, vanno nel brain di progetto corrente. La
promozione dal progetto al centrale resta esplicita.

Motivazione:

- Mantiene isolamento, ownership e provenance dei progetti.
- Sblocca il superpotere "cerca ovunque" su pattern, decisioni e soluzioni
  apprese in progetti passati.
- Evita di dover promuovere manualmente ogni conoscenza utile solo per poterla
  ritrovare.
- Rende il centrale una memoria operativa trasversale, non un contenitore
  monolitico.
- Mantiene il default di progetto leggibile e a basso rumore.
- Rende privacy e leakage controllabili tramite scope esplicito, opt-out per
  brain sensibili e trace dei risultati.

Regole:

- `talamus init` senza `--root` inizializza sempre la directory corrente.
- `talamus init --global` inizializza il centrale default.
- `talamus init --brain NAME` inizializza un brain globale nominato.
- La risoluzione per comandi diversi da `init` resta:
  `--root > --brain > --global > project ancestor > selected global > global default`.
- `selected global` e' gestito da `talamus brains use NAME`, salvato in un
  file di preferenza sotto `TALAMUS_HOME`, non dentro i progetti.
- Il registro globale contiene:
  - id stabile del brain.
  - nome.
  - path.
  - tipo: `central`, `project`, `archive`.
  - created_at, updated_at.
  - ultimo accesso.
  - relazione con progetto git, se presente.
- flag `federated`: se il brain partecipa all'indice federato.
- flag `sensitive`: se il brain deve essere escluso di default da `--scope all`.
- Le query devono riportare la provenienza dello scope: `[project]`, `[central]`,
  `[project:<name>]`, `[archive:<name>]`.
- `remember` in progetto scrive nel progetto.
- `remember --global` scrive nel centrale.
- `promote` copia o fonde note dal progetto al centrale preservando source refs,
  history e relazione di origine.
- L'indice federato e' un indice, non source truth. Puo' contenere title, alias,
  summary, retrieval_text, tags, domini, relation metadata, timestamps e pointer,
  ma le risposte devono leggere le note reali dal brain proprietario.
- Ogni risultato federato deve essere tracciabile a `brain_id`, root, note path e
  source refs del brain originario.
- Se un brain registrato e' mancante, bloccato o stale, la ricerca federata deve
  degradare con warning e non fallire l'intera query.
- Dedup cross-brain avviene a livello di ranking/presentazione; non fonde note
  tra brain senza promozione o review esplicita.

### 9.2 Auto-Estrazione Su Init

**Decisione:** `talamus init` non esegue scan costoso in silenzio. Offre scan
interattivo solo se il terminale e' TTY. Il percorso non interattivo richiede
flag espliciti.

Comandi:

```text
talamus init
talamus init --scan
talamus init --scan --profile docs
talamus init --scan --profile code
talamus init --scan --profile all
talamus scan .
talamus scan . --dry-run
talamus scan . --yes
talamus scan . --background
```

Profili:

- `docs`: Markdown, RST, TXT, DOCX, PDF testuali, HTML.
- `code`: file sorgente riconosciuti, README, config, test, manifest.
- `all`: `docs` + `code`.
- Default per prompt interattivo in repo git: `all`, ma sempre dopo dry-run.
- Default non interattivo: nessuno scan senza `--scan` o comando `scan`.

Scope:

- Rispetta `.gitignore`.
- Salta `.git`, `.talamus`, `node_modules`, `.venv`, `venv`, `dist`, `build`,
  `target`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, lockfile grandi,
  binari e file oltre soglia configurata.
- Include file non ignorati con estensioni testuali note.
- Riconosce repo git e registra commit HEAD, branch, dirty state e path relativo.

Codice:

- Non trattare codice come prosa.
- Estrarre schede di modulo, API pubbliche, responsabilita', dipendenze,
  entrypoint, test rilevanti e decisioni architetturali.
- Non creare una nota per ogni funzione privata.
- Non copiare codice sorgente nelle note salvo firme/API brevi necessarie.
- Ogni claim su codice punta a file e, quando possibile, range o simbolo.

Costo:

- Dry-run obbligatorio prima di scan interattivo.
- Stima numero file, bytes, token normalizzati, chiamate LLM, costo stimato per
  provider quando disponibile.
- Richiede conferma se costo stimato supera soglia config o se i file superano
  limite.
- Supporta `--max-files`, `--max-bytes`, `--max-cost`, `--profile`,
  `--exclude`, `--include`.

Esecuzione:

- Job persistente.
- Resume dopo crash.
- Report finale con note create/aggiornate, file saltati, errori, costo reale,
  durata, domini aggiornati e review items.

### 9.3 Ontologia Auto-Emergente

**Decisione:** mantenere i tipi fissi attuali come baseline compatibile, ma
aggiungere un sistema di induzione ontologica versionato e valutato.

La nuova ontologia ha due livelli:

1. **Core relation layer:** i tipi stabili usati dal prodotto e dall'MCP.
2. **Emergent schema layer:** tipi candidati, categorie, tassonomie e regole
   derivate dal corpus con evidence, confidence, versioni e review.

Un tipo emergente diventa "active" solo se supera soglie di supporto, stabilita',
precisione e utilita' sul retrieval. Se non supera le soglie resta in review o
research cache.

### 9.4 Retrieval A Scala

**Decisione:** passare da scansione O(N) a indici persistiti, mantenendo fallback
stdlib.

Core:

- Posting list persistite per termini.
- Metadata index per titolo, alias, tag, dominio, source, relation type.
- Adjacency index per grafo.
- Domain overview multi-livello.
- Cache dei risultati di routing quando query e indici non cambiano.

Implementazione:

- Primo backend: `sqlite3` stdlib con FTS5 se disponibile e tabelle normali per
  adjacency/metadata.
- Fallback: segmenti JSON posting-list quando FTS5 non e' disponibile.
- Nessun servizio esterno obbligatorio.

### 9.5 Bitemporale Completo

**Decisione:** introdurre valid-time come overlay su note, relazioni e claim,
senza spostare note Markdown.

Campi concettuali:

- `transaction_from`, `transaction_to`
- `valid_from`, `valid_to`
- `observed_at`
- `source_time`
- `invalidated_by`
- `confidence`
- `evidence`

Default:

- Se la fonte non esprime valid-time, `valid_from` resta vuoto o derivato da
  `source_time` con confidence esplicita.
- La vista corrente include elementi non invalidati e validi al tempo richiesto.
- Contraddizioni chiudono vecchi claim tramite overlay, non cancellano file.

### 9.6 UI Finale

**Decisione:** restare su Flet e SDK diretto per questa fase. Non introdurre
un'API locale obbligatoria. Aggiungere una modalita' web/dev per test e
screenshot.

La UI finale e' una workbench:

- Brain switcher e stato.
- Chat citata.
- Search.
- Wiki/note editor.
- Domain explorer.
- Graph view.
- Timeline/history.
- Ingest wizard.
- Review queues.
- Ontology lab.
- Settings/doctor.

### 9.7 CLI Finale

**Decisione:** costruire un linguaggio terminale proprietario e sobrio, senza
dipendenza obbligatoria da `rich`.

Requisiti:

- UTF-8 corretto su Windows.
- Colore ANSI solo se TTY e disattivabile con `--plain` o `NO_COLOR`.
- Output leggibile da umani per default.
- `--json` per tutti i comandi di lettura, stato, eval e job.
- Progress per job lunghi.
- Errori con causa, impatto e comando suggerito.
- Nessun comando distruttivo senza `--yes` o conferma TTY.

## 10. Requisiti Funzionali

### F1. Scoping E Multi-Brain

F1.1 `talamus init` crea un brain nella directory corrente quando `--root`,
`--brain` e `--global` non sono passati.

F1.2 `talamus where --json` restituisce:

```json
{
  "resolved_root": "C:/dev/Kortex",
  "scope": "project|global|named|explicit",
  "source": "--root|--brain|--global|project-ancestor|selected-global|default-global",
  "config_exists": true
}
```

F1.3 `talamus brains list --json` restituisce il registro completo.

F1.4 Nuovi comandi:

```text
talamus brains list
talamus brains use NAME
talamus brains info NAME
talamus brains rename OLD NEW
talamus brains delete NAME
talamus brains register PATH --name NAME --type project|central|archive
talamus brains set NAME --federated true|false
talamus brains set NAME --sensitive true|false
talamus brains index [--rebuild]
talamus brains index status
talamus brains promote NOTE --from project --to central
```

F1.5 Le operazioni cross-brain di promozione devono preservare id, provenance,
history e source refs. Le operazioni cross-brain di ricerca non copiano note:
ritornano pointer al brain proprietario.

F1.6 Ogni comando di lettura deve accettare una policy di scope:

```text
project-only
central-only
project+central
all
```

Default dentro un progetto: `project+central`.

Default dal brain centrale o da una UI globale: `all`, esclusi i brain marcati
`sensitive` salvo opt-in esplicito.

F1.7 `--all-brains` e' alias leggibile per `--scope all` su `ask`, `search`,
`recall`, `overview` e UI globale.

F1.8 L'indice federato locale deve supportare:

- `brain_id`.
- brain name.
- brain type.
- note id.
- note path.
- title.
- aliases.
- summary.
- retrieval_text.
- tags.
- domain ids/names.
- relation metadata.
- updated_at.
- index freshness marker.

F1.9 L'indice federato deve essere ricostruibile da ogni brain registrato senza
modificare i brain sorgente.

F1.10 Se un brain registrato non e' disponibile, i comandi federati devono
continuare sui brain disponibili e includere warning strutturato in `--json`.

F1.11 Il ranking federato deve includere un boost di prossimita' per il brain
corrente e per il centrale, cosi' `--scope all` non viene dominato da progetti
rumorosi.

F1.12 Il registry e l'indice federato devono essere lock-safe su Windows.

### F2. Init Scan E Repo Compilation

F2.1 `talamus scan --dry-run` produce un piano senza scrivere note.

F2.2 Il piano contiene:

- file inclusi per categoria.
- file esclusi con ragione.
- bytes totali.
- stima token.
- stima chiamate LLM.
- stima costo se il provider espone pricing o se config ha prezzi.
- durata stimata per fasce.
- profile usato.

F2.3 `talamus scan --yes` esegue il piano.

F2.4 `talamus scan --background` crea un job persistente.

F2.5 Nuovi comandi job:

```text
talamus jobs list
talamus jobs status JOB_ID
talamus jobs resume JOB_ID
talamus jobs cancel JOB_ID
talamus jobs logs JOB_ID
```

F2.6 Lo scan di codice produce note di questi tipi:

- Project Overview.
- Module.
- Public API.
- CLI Command Surface.
- Data Model.
- Test Coverage Map.
- Architecture Decision.
- Integration Point.
- Risk / Technical Debt.

F2.7 Ogni nota da codice include source refs con:

- path relativo.
- commit HEAD o `dirty`.
- hash file.
- simbolo o sezione quando disponibile.
- linea iniziale/finale se il parser le puo' derivare senza fragilita'.

F2.8 Lo scan non deve mai ingerire `.talamus`, `.git`, vendor, cache, binari o
segreti noti.

F2.9 Deve esistere una redaction pass per pattern di segreti prima di inviare
contenuto a LLM remoto.

F2.10 Se vengono rilevati possibili segreti, lo scan remoto si ferma e richiede
approvazione esplicita o provider locale.

### F3. Retrieval Economico A Scala

F3.1 Sostituire scansioni complete con indici persistiti per:

- termini note.
- titolo/alias.
- tag.
- domini.
- relazioni.
- source refs.

F3.2 `talamus reindex` ricostruisce indici in modo deterministico.

F3.3 `talamus doctor` segnala indici stale, backend usato e dimensioni.

F3.4 `talamus eval scale` genera o usa corpus di benchmark a 100, 1.000, 10.000
e 100.000 note.

F3.5 Metriche obbligatorie:

- p50/p95 retrieval locale.
- memoria peak stimata.
- dimensione indici.
- token del prompt di routing.
- chiamate LLM per ask.

F3.6 Retrieval flow finale:

```text
question
  -> normalize/query expansion locale
  -> overview route strutturato
  -> candidate retrieval da indexes
  -> graph expansion controllata
  -> rerank
  -> fit_to_budget
  -> answer from real notes
```

F3.7 Overview routing deve restituire JSON strutturato con domain ids, non nomi
matchati per sottostringa.

F3.8 Ogni dominio deve avere id stabile separato dal nome umano.

F3.9 Il fallback LLM query expansion avviene solo se retrieval locale fallisce o
confidence e' sotto soglia.

F3.10 `ask --trace` e `ask --json` devono mostrare:

- domini scelti.
- candidati locali.
- rerank scores.
- note lette.
- token context.
- perche' e' stato usato fallback.

### F4. Eval-Set Reale E Quality Gates

F4.1 Creare un eval-set reale versionato nel repo o in `examples/`, senza dati
privati.

F4.2 Minimo 120 casi:

- 30 domande dirette.
- 30 domande vaghe/non tecniche.
- 20 domande cross-source.
- 15 domande temporali.
- 15 domande su codice/progetto.
- 10 negative/no-answer.

F4.3 Ogni caso contiene:

```json
{
  "id": "retrieval-vague-001",
  "question": "dove spieghiamo perche il grafo non e' fonte di verita?",
  "relevant": ["Graph As Routing Index"],
  "expected_sources": ["docs/architecture.md"],
  "category": "vague",
  "notes": "The user asks indirectly for the design principle that graph metadata routes to real notes but is not cited as truth."
}
```

F4.4 `talamus eval` deve supportare filtro per categoria.

F4.5 Acceptance retrieval:

- recall@5 globale >= 0.85.
- MRR@5 globale >= 0.70.
- hit-rate@5 globale >= 0.90.
- recall@8 su domande vaghe >= 0.80.
- negative/no-answer precision >= 0.90.
- nessuna regressione > 0.02 assoluta rispetto alla baseline salvata senza
  decisione documentata.

F4.6 Acceptance citazioni:

- >= 0.95 delle risposte su casi answerable citano almeno una nota reale.
- >= 0.90 delle citazioni puntano a note che contengono source refs pertinenti.
- 0 risposte devono citare solo graph metadata.

### F5. Ontologia Auto-Emergente

F5.1 Introdurre un modulo `ontology_lab` o equivalente con responsabilita'
separate dal runtime MVP.

F5.2 Creare uno schema ontologico versionato:

```json
{
  "schema_id": "schema-20260610-ontology-v3",
  "version": 3,
  "created_at": "2026-06-10T14:30:00+02:00",
  "status": "candidate|active|deprecated",
  "relation_types": [
    {
      "id": "rel:depends-on",
      "name": "depends-on",
      "definition": "The subject requires the target to function, be understood, or be implemented correctly.",
      "inverse": "enables",
      "domain_hints": ["Software Component"],
      "range_hints": ["Dependency"],
      "examples": ["Overview routing depends-on Domain Overview"],
      "support": 42,
      "confidence": 0.87,
      "valid_from": "2026-06-10T14:30:00+02:00",
      "valid_to": null
    }
  ]
}
```

F5.3 Evidence objects:

```json
{
  "source_note": "Overview Routing",
  "source_ref": "docs/architecture.md#read-recall-ask",
  "subject": "ask",
  "predicate_surface": "routes through",
  "object": "Domain Overview",
  "context": "The ask layer routes a question through the domain overview before falling back to graph and BM25 retrieval.",
  "suggested_type": "uses",
  "confidence": 0.82,
  "created_at": "2026-06-10T14:35:00+02:00"
}
```

F5.4 Induction pipeline:

1. Collect relation evidence from notes, normalized sources and existing edges.
2. Extract candidate surface predicates and categories.
3. Canonicalize candidate predicates.
4. Cluster predicates into candidate relation types.
5. Generate definitions, inverses, domain/range hints and examples.
6. Score support, stability, coherence and retrieval utility.
7. Put candidates into review.
8. Promote passing candidates to active schema.
9. Version schema changes with temporal overlay.

F5.5 Signals allowed:

- existing typed relations.
- co-occurrence in note bodies.
- wikilinks and backlinks.
- source sections.
- title/alias/tags.
- graph motifs.
- LLM structured proposals.
- optional embeddings behind extra, never required in core.

F5.6 Required research deliverable:

`docs/research/2026-06-ontology-learning-review.md`

It must compare Talamus against:

- ontology learning.
- taxonomy induction.
- OpenIE.
- knowledge graph construction.
- GraphRAG.
- temporal knowledge graphs.
- agent memory systems.

The review must end with implementation decisions, not only a literature
summary.

F5.7 Metrics:

- **Coverage:** share of non-trivial edges assigned to a non-`related` active
  type.
- **Precision:** human-reviewed edge correctness.
- **Schema coherence:** human rating or pairwise cluster purity on sampled
  predicates.
- **Stability:** Jaccard similarity of schema across repeated runs on unchanged
  corpus.
- **Plasticity:** ability to add justified new types when corpus changes.
- **Retrieval utility:** MRR/recall lift vs fixed-type baseline.
- **Cost:** LLM calls and token per 1.000 notes.
- **Review burden:** candidate count requiring human approval per ingest.

F5.8 Acceptance ontology:

- Edge precision on reviewed sample >= 0.85.
- Schema stability on unchanged corpus >= 0.75 Jaccard.
- Retrieval MRR does not regress; target lift >= 0.05 absolute on ontology-heavy
  cases.
- `related` share decreases by >= 20% relative to baseline on real eval corpus,
  without precision dropping below threshold.
- Human review queue remains <= 10 candidates per 100 newly ingested notes by
  default thresholds.

F5.9 Commands:

```text
talamus ontology status
talamus ontology induce
talamus ontology review
talamus ontology apply CANDIDATE_ID
talamus ontology reject CANDIDATE_ID
talamus ontology eval --cases FILE
talamus ontology history
talamus ontology export
```

F5.10 Runtime retrieval must prefer active schema. Candidate schema can be used
only when `--experimental-ontology` or config opt-in is enabled.

### F6. Bitemporale Completo

F6.1 Add valid-time fields to relations/claims without breaking existing cache.

F6.2 Add migration from cache version 1 to new version.

F6.3 `talamus history` must distinguish:

- transaction history: when Talamus changed records.
- valid history: when the claim was true in the represented world.

F6.4 New commands:

```text
talamus timeline "<title>"
talamus as-of "2026-01" ask "what was the retrieval design before reranking?"
talamus as-of "2026-01-15T12:00:00+01:00" read "<title>"
```

F6.5 Date parsing:

- year.
- year-month.
- date.
- datetime with timezone.
- datetime without timezone interpreted as local timezone with warning in trace.

F6.6 Invalidations:

- A correction or contradiction creates overlay entries closing old claims.
- Old notes remain readable.
- Current retrieval excludes invalidated facts unless temporal query asks for
  them.

F6.7 Acceptance:

- Unit tests for partial date, timezone, date-only and invalid date errors.
- Temporal eval cases pass with recall@5 >= 0.80.
- Contradicted fact does not appear in current answer unless cited as historical.

### F7. Verificabilita' Attiva

F7.1 `verify` must support batch mode:

```text
talamus verify --all
talamus verify --stale
talamus verify --source SOURCE_ID
```

F7.2 Add stale/provenance status per note:

- source missing.
- source changed.
- source unreachable.
- low extraction confidence.
- low verification confidence.
- needs human review.

F7.3 Add review queue:

```text
talamus review list
talamus review show ITEM_ID
talamus review apply ITEM_ID
talamus review reject ITEM_ID
```

F7.4 Correction from source must never silently overwrite without preserving
history.

F7.5 UI must expose verification status and review actions.

F7.6 Acceptance:

- Batch verify on demo brain produces deterministic report.
- Applying a correction appends history.
- Rejected correction remains logged.
- Missing source yields actionable error and review item, not crash.

### F8. CLI Definitiva

F8.1 Add a top-level dashboard when running `talamus`.

Dashboard sections:

- active brain.
- scope.
- notes count.
- source count.
- index freshness.
- overview status.
- ontology status.
- pending jobs.
- review items.
- next recommended command.

F8.2 Add `--plain`, `--no-color`, `--json`, `--verbose`, `--trace`.

F8.3 Existing commands must keep working or emit migration guidance.

F8.4 Command help must include examples.

F8.5 Long commands must show:

- stage.
- current file.
- processed/total.
- elapsed.
- estimated remaining when possible.
- cost so far when LLM provider reports usage or estimate is available.

F8.6 Errors must follow:

```text
error: short human message
cause: concrete cause
fix: exact command or config change
```

F8.7 Machine JSON errors must include:

```json
{
  "ok": false,
  "error": {
    "code": "brain_not_initialized",
    "message": "project brain is not initialized",
    "cause": "no talamus.json found at C:/dev/Kortex",
    "fix": "run `talamus init` or pass `--global`"
  }
}
```

F8.8 Acceptance:

- No mojibake on Windows PowerShell.
- All read/status/eval/job/review commands support `--json`.
- Snapshot tests for representative CLI output.
- `talamus --help` and every subcommand help render under 100 columns.

### F9. UI Definitiva

F9.1 Add `talamus ui --web --port PORT` for deterministic testing.

F9.2 Main IA:

- Home.
- Chat.
- Search.
- Notes.
- Domains.
- Graph.
- Timeline.
- Ingest.
- Review.
- Ontology.
- Settings.

F9.3 Home:

- active brain switcher.
- health summary.
- last jobs.
- review count.
- recent notes.
- suggested actions.

F9.4 Chat:

- streamed/progress answer state.
- citations clickable.
- source inspector.
- route trace collapsible.
- no-answer state.
- temporal mode.
- scope toggle: progetto, centrale, progetto+centrale, tutti i brain.

F9.5 Search:

- instant local search.
- filters by domain, source, type, time, brain scope.
- result score explanation.

F9.6 Note view/editor:

- Markdown render.
- wikilink hover preview.
- edit mode.
- source refs panel.
- relation panel.
- history panel.
- reindex after save.

F9.7 Domains:

- multi-level overview.
- domain membership.
- domain confidence.
- stale domain warning.

F9.8 Graph:

- typed edges.
- filters.
- current/historical toggle.
- focus selected note.
- source and relation inspector.

F9.9 Ingest:

- file picker.
- folder picker.
- URL input.
- scan dry-run.
- cost estimate.
- progress.
- failures with reasons.
- resume/cancel.

F9.10 Review:

- duplicate concepts.
- correction suggestions.
- ontology candidates.
- stale sources.
- low-confidence notes.

F9.11 Ontology Lab:

- active schema.
- candidate schema.
- candidate type detail.
- examples/evidence.
- metrics.
- apply/reject.
- history.

F9.12 Settings:

- provider.
- model.
- context budget.
- scan defaults.
- privacy/redaction.
- brain registry.
- doctor.

F9.13 Visual requirements:

- Workbench, not landing page.
- Dense but calm layout.
- No decorative filler.
- Clear typography hierarchy.
- Works at 1280x800 desktop.
- Works at narrow 390px width for web/mobile fallback.
- No text overlap.
- Loading, empty, error and disabled states for every surface.

F9.14 Acceptance:

- UI launches from demo brain.
- UI launches from empty brain.
- UI can ingest a small Markdown file.
- UI can ask and show citations.
- UI can open a note through search and wikilink.
- UI can show review queue empty and populated.
- UI can run in web test mode and produce screenshots.
- Type-check passes with UI extra.

### F10. MCP E Agent Memory

F10.1 MCP tools must expose brain scope explicitly: project, central,
project+central, all.

F10.2 Required read tools:

- `search`
- `read_note`
- `recall`
- `overview`
- `neighbors`
- `history`
- `sources`
- `ontology_status`

F10.3 Required write tools:

- `remember`
- `ingest_text`
- `propose_note`
- `review_list`
- `review_apply`
- `review_reject`

F10.4 Write policy:

- `remember` applies worth-remembering gate.
- default write target is project brain.
- global write requires explicit scope.
- uncertain memories go to review, not directly to notes.

F10.5 Agent capture must record:

- transcript source.
- project path.
- git branch/commit if available.
- diff hash.
- model/provider if provided.
- reason for memory capture or skip.

F10.6 Acceptance:

- MCP tests cover every tool schema.
- Agent read path never returns graph metadata as source truth without note/source
  content.
- `remember` skip/apply decisions are logged and testable.

### F11. Source Coverage

F11.1 Keep existing PDF/DOCX/HTML/text/URL support.

F11.2 Add OCR as optional extra.

F11.3 Add PPTX/XLSX/CSV/EPUB as optional adapters when they can preserve
provenance and locator.

F11.4 Add media only behind explicit extras:

- image caption/OCR.
- audio transcription.
- video transcript/subtitles.

F11.5 Every adapter must implement:

- supported extensions.
- extraction.
- normalized package output.
- locator model.
- quality report.
- failure reason.

F11.6 Acceptance:

- Adapter tests with tiny fixtures.
- No optional adapter dependency imported by core at import time.
- `doctor` reports missing extras with install command.

### F12. Release, Docs E Packaging

F12.1 Update README to distinguish shipped, experimental and roadmap features.

F12.2 Docs must include:

- quickstart.
- CLI reference.
- config.
- architecture.
- eval.
- multi-brain.
- init scan.
- ontology.
- temporal model.
- UI.
- MCP.
- privacy and redaction.
- troubleshooting.

F12.3 Add release checklist.

F12.4 Add migration docs for cache/schema.

F12.5 Add native packaging path:

- Python package.
- optional standalone CLI build.
- Flet builds for desktop.

F12.6 Acceptance:

- Docs build.
- README commands match actual CLI.
- No claim in README lacks shipped/experimental/roadmap label.

## 11. Non-Functional Requirements

### 11.1 Performance

Retrieval local, excluding LLM answer generation:

- 100 notes: p95 <= 150 ms.
- 1.000 notes: p95 <= 300 ms.
- 10.000 notes: p95 <= 1.2 s.
- 100.000 notes: p95 <= 5 s.

Index build:

- Incremental reindex must avoid rebuilding unaffected segments when possible.
- Full rebuild of 10.000 notes must complete without exhausting 16 GB RAM.

UI:

- Cold launch on demo brain <= 5 s.
- Cached navigation between views <= 150 ms perceived delay.
- Search input result update <= 300 ms at 10.000 notes.

CLI:

- Status commands <= 500 ms on normal brain.
- `doctor` <= 2 s excluding external tool checks.

### 11.2 Cost

- Ask should use at most 2 LLM calls in normal path: domain route plus answer.
- Query expansion is fallback only.
- Retrieval local must not call LLM.
- Ingest/scan dry-run estimates must be within 25% of actual token usage on
  sampled runs where provider usage is observable.
- Context sent to answer model must respect `TALAMUS_CONTEXT_BUDGET`.
- Overview routing prompt must remain bounded through multi-level maps.

### 11.3 Reliability

- Jobs persist before first expensive call.
- Job state survives process crash.
- File writes use atomic replace when practical.
- Registry writes are lock-safe.
- Corrupt cache yields actionable error and rebuild path.
- Imports of optional extras cannot break core CLI.

### 11.4 Security And Privacy

- Local-first default.
- Remote LLM use must be visible in config/doctor.
- Scan redacts likely secrets before remote provider calls.
- `.env`, key files and secret-like files are excluded by default.
- Logs must not include secret values.
- MCP write tools require explicit operation and scope.
- Federated search must respect `sensitive=false|true` and must not include
  sensitive brains in `--scope all` unless the user passes an explicit override.

### 11.5 Compatibility

- Windows, macOS, Linux in CI.
- Python >= 3.11.
- PowerShell output must preserve UTF-8.
- Path handling must support spaces and non-ASCII paths.

### 11.6 Maintainability

- Core modules remain focused.
- UI must not duplicate retrieval logic.
- CLI must not implement business logic outside SDK calls.
- New cache formats require version and migration.
- Every new public SDK function has type hints and tests.

## 12. Research Plan: Ontologia Auto-Emergente

### 12.1 Research Question

Can Talamus induce a stable, useful and human-comprehensible ontology from a
local corpus without prescribing the full type system upfront, while keeping the
system cheap, verifiable and temporally evolvable?

### 12.2 Hypotheses

H1. A corpus-specific emergent schema can improve retrieval MRR on vague and
cross-source questions compared with fixed relation types.

H2. Stable relation types can be induced from a combination of LLM-structured
evidence, graph motifs, wikilinks, aliases and source contexts without requiring
cloud-only embeddings.

H3. Schema evolution can be made safe by separating candidate, active and
deprecated relation types, and by requiring stability/support thresholds before
promotion.

H4. Versioning the ontology schema itself improves temporal questions and
prevents drift from corrupting existing knowledge.

H5. Human review burden can stay low if candidate generation is filtered by
support, confidence and retrieval utility.

### 12.3 Method

1. Establish baseline with current fixed relation types.
2. Build real eval corpus.
3. Collect relation evidence from current notes and source snippets.
4. Run candidate type induction on a static corpus.
5. Re-run induction multiple times to measure stability.
6. Replay incremental ingests to measure drift.
7. Compare retrieval with:
   - fixed types only.
   - emergent candidate types disabled.
   - active emergent schema.
   - active schema plus temporal overlay.
8. Human-review sampled edges and type definitions.
9. Promote only candidates passing thresholds.
10. Document findings and product decisions.

### 12.4 Experiments

E1. **Static Stability:** same corpus, multiple induction runs, measure schema
Jaccard, edge assignment stability and type rename/split/merge rate.

E2. **Incremental Drift:** ingest batches chronologically, measure how often
existing types change and whether new types are justified.

E3. **Retrieval Utility:** run eval cases with baseline fixed ontology and active
emergent ontology.

E4. **Human Precision:** sample edges and candidate types for human judgment.

E5. **Cost Curve:** measure LLM calls and tokens per 100, 1.000 and 10.000
notes.

E6. **Temporal Schema:** create a corpus where concepts and relation meanings
change over time; verify schema history and as-of retrieval.

E7. **Domain Transfer:** run on at least two different corpora, for example a
software repo brain and a research notes brain, to verify the schema is not
overfit to one domain.

### 12.5 Metrics

Ontology quality:

- relation edge precision.
- candidate type precision.
- schema stability Jaccard.
- type support distribution.
- non-`related` coverage.
- review burden.

Retrieval utility:

- recall@k.
- MRR.
- hit-rate.
- negative precision.
- citation validity.

Temporal quality:

- as-of correctness.
- invalidated fact exclusion.
- schema history correctness.

Cost:

- tokens per induction.
- calls per induction.
- wall-clock time.
- review items per 100 notes.

### 12.6 Promotion Rules

A candidate relation type can become active only if:

- support >= configured minimum, default 8 evidence items across at least 3
  source notes.
- edge precision sample >= 0.85.
- schema stability contribution does not reduce global stability below 0.75.
- retrieval metrics do not regress.
- name and definition are non-conflicting with active schema.
- examples point to real source refs.

A type is deprecated, not deleted, if:

- it is superseded by a better type.
- precision drops below threshold.
- it becomes too broad.
- it is merged into another type.

Deprecation preserves history and migration mapping.

## 13. UX Requirements: CLI

### 13.1 Personality

The CLI should feel like an expert local tool: direct, elegant, fast, and clear.
It should not feel like a Python script dumping internals.

### 13.2 Example Dashboard

```text
Talamus
Brain      C:\dev\Project  [project]
Central    C:\Users\Giovanni\talamus\default
Notes      428      Sources  91      Reviews  3
Indexes    fresh    Ontology active   Jobs     1 running

Next
  talamus jobs status scan-20260610-1432
  talamus review list
  talamus ask "what changed in the retrieval design?"
```

### 13.3 Example Error

```text
error: project brain is not initialized
cause: no talamus.json found at C:\dev\Kortex
fix: run `talamus init` or pass `--global`
```

### 13.4 Example Scan Dry-Run

```text
Scan plan for C:\dev\Kortex
Profile     all
Files       184 included, 3,912 skipped
Estimate    1.8M input tokens, 420 LLM calls
Cost        provider does not expose pricing; set llm_pricing in config
Safety      2 possible secret files excluded

Run
  talamus scan . --profile all --yes
```

### 13.5 Required Command Groups

```text
talamus init
talamus scan
talamus ask
talamus search
talamus read
talamus overview
talamus ontology
talamus timeline
talamus verify
talamus review
talamus jobs
talamus brains
talamus mcp
talamus ui
talamus eval
talamus doctor
```

## 14. UX Requirements: UI

### 14.1 Product Shape

The UI is a local knowledge workbench. It should not be a marketing page. The
first viewport after launch is the actual brain state and working surface.

### 14.2 Layout

Three-zone desktop layout:

1. Left rail/sidebar: brain, navigation, domains.
2. Main pane: current work surface.
3. Right inspector: citations, source, relations, history, trace.

On narrow widths:

- left rail collapses.
- inspector becomes bottom sheet or tab.
- content remains readable.

### 14.3 Visual Language

- Quiet, dense, professional.
- Neutral base with restrained accent colors for status, relation types and
  warnings.
- No decorative gradients, orbs or marketing hero.
- Text never overlaps controls.
- Buttons use icons where clear.
- Cards only for repeated items, modals or framed tools.
- Graph view is functional, not decorative.

### 14.4 Critical Flows

Flow A: First project brain

1. Launch UI in repo.
2. See no brain.
3. Click initialize.
4. See scan dry-run.
5. Confirm scan.
6. Watch job progress.
7. Ask first question.
8. Open cited note.

Flow B: Daily agent memory

1. Open project.
2. See new captured sessions in review.
3. Apply useful memory.
4. Promote durable concept to central brain.
5. Ask a project question with central fallback.
6. Ask a cross-project question with federated search across registered brains.

Flow C: Ontology review

1. Open ontology lab.
2. See candidate type with examples.
3. Inspect evidence and source snippets.
4. Apply candidate.
5. Run ontology eval.
6. See retrieval metric change.

Flow D: Temporal verification

1. Ask current question.
2. Toggle as-of date.
3. See answer change.
4. Inspect invalidated claim and source.

## 15. Data Model Additions

### 15.1 Brain Registry

Location:

```text
<TALAMUS_HOME>/registry.json
```

Schema:

```json
{
  "version": 1,
  "selected": "default",
  "brains": [
    {
      "id": "brain-default",
      "name": "default",
      "path": "C:/Users/Giovanni/talamus/default",
      "type": "central",
      "federated": true,
      "sensitive": false,
      "created_at": "2026-06-10T00:00:00+02:00",
      "updated_at": "2026-06-10T00:00:00+02:00",
      "last_accessed_at": "2026-06-10T00:00:00+02:00",
      "project": null
    }
  ]
}
```

### 15.2 Federated Index

Location:

```text
<TALAMUS_HOME>/federation/index.sqlite
<TALAMUS_HOME>/federation/index.json
```

`index.sqlite` is preferred when stdlib SQLite/FTS5 is available. `index.json`
is the deterministic fallback.

The federated index stores searchable metadata and pointers, not source truth:

```json
{
  "brain_id": "brain-kortex",
  "brain_name": "kortex",
  "brain_type": "project",
  "note_id": "overview-routing",
  "note_path": "C:/dev/Kortex/notes/Overview Routing.md",
  "title": "Overview Routing",
  "aliases": ["Domain Routing"],
  "summary": "Routes questions through a bounded domain map before reading notes.",
  "retrieval_text": "overview routing domain map ask retrieval",
  "tags": ["retrieval", "overview"],
  "domains": ["retrieval"],
  "relations": [{"type": "uses", "target": "Domain Overview"}],
  "updated_at": "2026-06-10T14:30:00+02:00",
  "source_refs_count": 2,
  "fresh": true
}
```

The answer path must open `note_path` in the owning brain before citing.

### 15.3 Job Store

Location:

```text
.talamus/cache/jobs/<job_id>.json
.talamus/cache/jobs/<job_id>.log
```

Job kinds:

- scan.
- ingest.
- verify.
- ontology_induction.
- eval.
- export/import.

States:

- queued.
- running.
- paused.
- completed.
- failed.
- cancelled.

### 15.4 Review Queue

Location:

```text
.talamus/cache/review/<item_id>.json
```

Item kinds:

- duplicate_concept.
- correction.
- ontology_candidate.
- stale_source.
- low_confidence_note.
- scan_safety.

### 15.5 Ontology Schema

Location:

```text
.talamus/cache/ontology/schema.json
.talamus/cache/ontology/evidence.jsonl
.talamus/cache/ontology/history.jsonl
```

`ontology.json` remains the active concept-edge index for runtime compatibility.

### 15.6 Temporal Overlay

Location:

```text
.talamus/cache/timeline/claims.jsonl
.talamus/cache/timeline/relations.jsonl
.talamus/cache/timeline/schema.jsonl
```

The overlay points to note ids, relation ids, source refs and ontology schema ids.

## 16. Milestones

Each milestone must be shippable, documented and gate-green. Do not merge a
milestone that leaves the product in a partially migrated state.

### M0. Measurement Baseline

Goal: know the current truth before changing architecture.

Scope:

- Run current test suite.
- Create benchmark fixture brain.
- Create initial real eval-set.
- Measure retrieval quality, latency and token/call counts.
- Record known UI runtime behavior.

Gate:

- `python dev.py` passes or failures are documented as pre-existing.
- `talamus eval` runs on real cases.
- Baseline report saved in `docs/benchmarks/`.

### M1. Scoping, Brain Registry And Federated Index

Goal: fix `init`, implement registry, make brain resolution explicit and make
local cross-brain search possible from the central hub.

Scope:

- Fix `talamus init` current-directory behavior.
- Add registry.
- Add `brains` subcommands.
- Add `where --json`.
- Add federated index build/status.
- Add `--scope` and `--all-brains` to read commands.
- Add tests for project/global/named precedence.
- Add tests for federated read over two fixture brains.

Gate:

- CLI smoke tests pass on temp dirs.
- No command writes to global default unexpectedly.
- `talamus search --all-brains` returns results with `brain_id` and then reads
  real notes from the owning brain.

### M2. Jobs, Review Queue And Progress

Goal: create substrate for long-running safe operations.

Scope:

- Job store.
- Review queue.
- Progress abstraction.
- CLI job commands.
- Atomic writes and recovery.

Gate:

- Simulated crash resumes.
- Cancelled job does not corrupt notes.

### M3. Init Scan And Repo Compilation

Goal: make existing repos useful quickly and safely.

Scope:

- `scan --dry-run`.
- profile docs/code/all.
- `.gitignore` respect.
- secret redaction.
- code-aware extraction.
- cost estimate.
- job execution.

Gate:

- Scan this repository in dry-run.
- Scan a fixture repo and produce useful notes.
- No vendor/cache files ingested.

### M4. Persistent Retrieval Indexes

Goal: remove O(N) query bottlenecks.

Scope:

- term/title/alias posting lists or sqlite backend.
- adjacency index.
- domain id routing.
- `ask --trace`.
- scale eval.

Gate:

- Latency targets pass through 10.000-note benchmark.
- Retrieval metrics do not regress.

### M5. Ontology Lab V1

Goal: turn ontology into measurable research/product loop.

Scope:

- evidence collection.
- candidate induction.
- schema versioning.
- review commands.
- ontology eval.
- research review document.

Gate:

- Fixed baseline and emergent schema compared on eval.
- Candidate promotion rules enforced.
- Metrics report generated.

### M6. Full Temporal Model

Goal: valid-time plus transaction-time across claims and relations.

Scope:

- temporal overlay.
- date parser.
- claim invalidation.
- temporal ask/read.
- migration.

Gate:

- Temporal eval cases pass.
- Current retrieval excludes invalidated claims.

### M7. Active Verifiability

Goal: make verification continuous and visible.

Scope:

- batch verify.
- stale source detection.
- verification review items.
- confidence propagation.
- UI/CLI surfacing.

Gate:

- Batch verify fixture passes.
- Corrections preserve history.

### M8. Final CLI

Goal: make the terminal product-grade.

Scope:

- dashboard.
- output design.
- `--json` coverage.
- `--trace`.
- command help.
- snapshot tests.

Gate:

- Windows PowerShell UTF-8 verified.
- Help/status snapshots stable.

### M9. Final UI Workbench

Goal: make UI complete and runtime-verified.

Scope:

- web test mode.
- Home, Chat, Search, Notes, Domains, Graph, Timeline, Ingest, Review,
  Ontology, Settings.
- source inspector.
- graph view.
- ingest wizard.
- review flows.
- screenshots.

Gate:

- UI smoke tests pass.
- Screenshots reviewed at desktop and narrow widths.
- No duplicated business logic.

### M10. MCP And Agent Memory Finalization

Goal: make Talamus reliable as agent memory.

Scope:

- MCP schemas for new read/write tools.
- scope-aware writes.
- memory promotion.
- capture logs.
- agent docs.

Gate:

- MCP integration tests pass.
- Agent protocol docs match tool schemas.

### M11. Release Hardening

Goal: make product publicly defensible.

Scope:

- docs.
- migrations.
- packaging.
- install verification.
- changelog.
- README claim audit.
- example brains/eval.

Gate:

- Clean install works.
- Docs build.
- CI green.
- README has no unlabelled roadmap claims.

## 17. Acceptance Criteria Finale

The phase is complete only when all criteria below are true.

### 17.1 Functional

- `talamus init` initializes current directory by default.
- `talamus init --scan` can compile an existing repo after dry-run confirmation.
- Multi-brain local ownership plus federated read workflow works end to end.
- Ask reads real notes and cites them.
- Temporal ask can answer as-of questions.
- Ontology lab can induce, review, promote and evaluate candidate types.
- UI supports daily core workflows.
- MCP supports read/write memory with explicit scope.

### 17.2 Measurement

- Real eval-set has at least 120 cases.
- Retrieval meets thresholds.
- Ontology metrics report generated.
- Scale benchmark generated through at least 10.000 notes; 100.000 if hardware
  permits.
- Cost report covers ingest, scan, overview, ask, verify and ontology induction.

### 17.3 Quality

- `python dev.py` passes.
- `ruff` passes.
- `mypy` passes.
- unittest suite passes.
- CI green on Windows, macOS, Linux.
- UI extra type-check passes.
- Docs build.

### 17.4 Safety

- No graph metadata is used as answer source truth.
- No generated caches or `.claude/` files committed.
- Secret-like files excluded by scan default.
- Remote LLM use visible and configurable.
- Destructive commands require confirmation or `--yes`.

### 17.5 UX

- CLI no-arg dashboard is useful on empty, demo and real brain.
- Errors are actionable.
- UI launches on empty and demo brain.
- UI has no blocking silent operations.
- UI shows citations, source refs and review items clearly.

## 18. Da Verificare Vs Da Costruire

### 18.1 Da Verificare Prima Di Costruire Sopra

| Area | Verifica | Metodo | Output |
| --- | --- | --- | --- |
| Retrieval reale | Qualita' su domande non sintetiche | Eval-set 120 casi | `docs/benchmarks/retrieval-baseline.md` |
| Scala retrieval | Latenza/costo a N note | `talamus eval scale` | report JSON + markdown |
| Overview cost | Token routing a 100/1k/10k/100k | trace ask | curva token |
| Ontologia baseline | Precisione/stabilita' tipi fissi | sample review + repeated run | report baseline |
| Estrazione | Fedelta' e atomicita' note | spot-check con rubric | report |
| Init scoping | Bug current dir/global | test CLI temp dirs | test failing poi passing |
| UI runtime | Flet reale | launch web/desktop | screenshots/log |
| Bitemporale | date-only/timezone/string compare | unit tests | failing tests |
| Costo LLM | calls/tokens per workflow | provider wrappers/estimator | cost ledger |
| MCP safety | tool read/write scope | schema tests | test report |

### 18.2 Da Costruire

| Area | Build |
| --- | --- |
| Multi-brain | registry, use/info/rename/delete/promote, federated index, project+central query, all-brains query |
| Init scan | dry-run, profiles, redaction, job, code-aware extraction |
| Jobs | persistent job store, resume, cancel, logs |
| Review | duplicate/correction/ontology/stale queues |
| Retrieval | persistent indexes, structured overview routing, trace |
| Ontologia | evidence, schema induction, metrics, review, history |
| Tempo | valid-time overlay, robust as-of, temporal ask |
| Verifica | batch verify, stale detection, confidence propagation |
| CLI | dashboard, progress, JSON coverage, snapshot tests |
| UI | workbench complete, graph, ingest, review, ontology, timeline |
| MCP | scope-aware tools, history/sources/ontology, write policy |
| Release | docs, packaging, migrations, benchmark artifacts |

## 19. Rischi E Mitigazioni

### R1. L'ontologia Emergente Diventa Rumorosa

Mitigazioni:

- Candidate layer separato da active layer.
- Promotion thresholds.
- Human review.
- Metrics obbligatorie.
- Deprecation invece di deletion.
- Retrieval fallback su baseline.

### R2. Costi LLM Troppo Alti Su Repo Grandi

Mitigazioni:

- Dry-run.
- Budget e soglie.
- Batching.
- Incremental hash cache.
- Provider locale consigliato per scan sensibili.
- Code-aware summaries invece di note per funzione.

### R3. Indici Persistiti Aumentano Complessita'

Mitigazioni:

- Backend stdlib.
- Fallback JSON.
- Rebuild deterministico.
- Manifest versionato.
- Tests di migrazione.

### R4. UI Duplica Logica Del Core

Mitigazioni:

- SDK functions come unico punto di verita'.
- UI integration tests sui flussi, unit tests nel core.
- Review architetturale prima di merge.

### R5. Temporalita' Rompe Modello Semplice

Mitigazioni:

- Overlay separato.
- Default current view semplice.
- Temporal commands espliciti.
- Migrazione compatibile.

### R6. Scan Rischia Di Inviare Segreti A LLM Remoto

Mitigazioni:

- Respect `.gitignore`.
- Exclusion defaults.
- Secret scanner.
- Stop-and-confirm.
- Local provider recommendation.
- Logs senza valori segreti.

### R7. Prodotto Promette Troppo Nel README

Mitigazioni:

- Claim audit.
- Label `shipping`, `experimental`, `roadmap`.
- Acceptance criteria prima di spostare una feature a shipping.

### R8. Federazione Cross-Brain Rumorosa O Troppo Permissiva

Mitigazioni:

- Scope prudente dentro i progetti: `project+central`, non `all`.
- `--all-brains` esplicito per ricerche trasversali.
- Boost di ranking per brain corrente e centrale.
- Flag `sensitive` per escludere brain da federazione default.
- Trace obbligatorio di `brain_id`, scope e motivo del ranking.
- Dedup solo a livello di presentazione; nessuna fusione cross-brain senza
  review o promozione.
- Warning strutturati per brain mancanti, stale o esclusi.

## 20. Test Strategy

### 20.1 Unit Tests

- path/scoping.
- registry.
- job state transitions.
- review queue.
- scan include/exclude.
- redaction.
- indexes.
- structured overview routing.
- ontology evidence and schema scoring.
- temporal parser.
- valid-time filtering.
- CLI JSON schemas.

### 20.2 Integration Tests

- init project brain.
- init global brain.
- scan fixture repo.
- ingest folder with failures.
- ask with trace.
- verify batch.
- ontology induce/review/apply.
- project+central retrieval.
- federated all-brains retrieval with a missing/stale brain warning.
- MCP tool calls.

### 20.3 Eval Tests

- retrieval eval real set.
- ontology eval.
- temporal eval.
- scale eval.
- cost eval.

### 20.4 UI Tests

- launch web test mode.
- screenshot home/chat/search/note/ingest/review/ontology.
- click wikilink.
- run dry-run from UI.
- empty/error/loading states.

### 20.5 Manual Verification

- Windows PowerShell UTF-8.
- Flet desktop launch.
- install in clean venv.
- optional extras install.
- MCP config with real client when available.

## 21. Definition Of Done Per Il Modello Esecutore

The implementing model must not claim completion until it has:

1. Read this PRD and the linked architecture docs.
2. Produced a task plan mapped to milestones M0-M11.
3. Preserved existing user changes.
4. Added tests before or with behavioral changes.
5. Run relevant tests after each milestone.
6. Updated docs with shipped/experimental labels.
7. Generated benchmark/eval artifacts.
8. Verified CLI UX on Windows-compatible paths.
9. Verified UI runtime in web or desktop mode.
10. Confirmed no generated caches or private artifacts are staged.
11. Reported residual risks and metrics honestly.

## 22. Suggested Execution Order For A One-Pass High-Capacity Model

Even if one model can execute the full phase in one pass, it must preserve
incremental gates:

1. M0 measurement baseline.
2. M1 scoping/registry.
3. M2 jobs/review substrate.
4. M3 init scan.
5. M4 retrieval scale.
6. M5 ontology lab.
7. M6 temporal model.
8. M7 active verifiability.
9. M8 CLI finalization.
10. M9 UI finalization.
11. M10 MCP agent memory.
12. M11 release hardening.

Each milestone should be internally committed or checkpointed in a way the user
can review. If automatic commits are not desired, the model must provide exact
staging groups.

## 23. Open Questions Closed By This PRD

1. **Multi-brain:** choose local project ownership plus central federated read
   hub; not cloud/team federation, and not automatic central absorption of every
   project note.
2. **Init scan:** safe opt-in scan with dry-run; no silent expensive extraction.
3. **Code ingestion:** include code through specialized summaries, not prose
   extraction.
4. **Ontologia:** fixed types remain baseline; emergent schema becomes
   candidate/active/deprecated research-product layer.
5. **Scale:** persistent stdlib indexes, not O(N) scans.
6. **Bitemporale:** valid-time overlay plus transaction history.
7. **UI:** Flet workbench over SDK, no required API.
8. **CLI:** product-grade terminal design without mandatory rich dependency.
9. **Verification vs build:** M0 verifies first; later milestones build only on
   measured baseline.

## 24. Final Product Claim

After this PRD is implemented, the honest claim should be:

> Talamus is a local-first knowledge compiler for humans and AI agents. It turns
> real sources into editable, cited concept notes; builds graph, lexical,
> temporal and ontological indexes as routing layers; answers from real notes;
> preserves source truth and history; and learns a measured, reviewable ontology
> that improves retrieval without surrendering local control.

This claim is allowed only if the acceptance criteria in section 17 pass.
