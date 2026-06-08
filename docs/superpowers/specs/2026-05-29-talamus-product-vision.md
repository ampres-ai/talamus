# Talamus — Visione di Prodotto (bussola a 6 mesi)

Data: 2026-05-29
Stato: visione approvata sezione per sezione. Documento-bussola.

## Come si usa questo documento

Questo non è un piano tecnico né un elenco di task. È la **bussola**: descrive come
sarà Talamus nella sua **versione finale a 6 mesi**, in modo che ogni scelta tecnica
di oggi non chiuda porte agli aggiornamenti di domani.

Regola d'oro: se uno sviluppo contraddice un principio o una scelta scritta qui,
si ferma e si rivede questo documento *prima* di procedere. L'architettura tecnica
vera e propria verrà scritta a parte, appoggiandosi a questa visione.

Le decisioni qui contenute sono state prese una per una con domande mirate. Dove
una scelta era ambiziosa, è segnalata; il *come* realizzarla in modo sostenibile è
demandato all'architettura.

---

# Parte I — Identità: cos'è e per chi

## 1. Visione e frase-bussola

**Talamus è una memoria unica, local-first, condivisa tra una persona e i suoi
agenti AI.**

La tua conoscenza curata a mano e la memoria dei tuoi agenti AI **sono la stessa
cosa**, nello stesso substrato. I due usi sono di pari grado:

- come **second brain** lo alimenti tu a mano (appunti, documenti, fonti) e gli fai
  domande con risposte citate;
- come **memoria per agenti** i tuoi assistenti AI vi leggono dentro mentre lavorano
  e vi depositano il frutto del loro lavoro, che diventa nuova conoscenza.

Concettualmente Talamus è un **compilatore di conoscenza**: trasforma materiale
grezzo (documenti, appunti, sessioni di lavoro con gli agenti) in **schede
source-grounded**, costruisce una **mappa** (ontologia + grafo) che fa da indice di
navigazione, e permette a umani e agenti di **leggere i file reali e rispondere con
citazioni**, senza dover ingoiare tutta la memoria.

La forza del prodotto è l'**efficienza di token senza perdere fedeltà alla fonte**:
non si legge tutta la wiki, si recupera un piccolo insieme di schede pertinenti, si
leggono quelle reali, si risponde citando.

## 2. Utenti e scenari d'uso

**Utente primario (per cui ottimizziamo a 6 mesi):** il **power-user con agenti AI**
— sviluppatori e professionisti che usano agenti (Claude Code, Codex, ecc.) e
vogliono che ricordino tra una sessione e l'altra e attingano al proprio brain.

Scenario di riferimento ("A ora"):
1. Lavoro con un agente su un progetto.
2. L'agente, durante il lavoro, consulta Talamus ("cosa sappiamo già su X?").
3. A fine sessione, la conversazione e il lavoro prodotto (codice, modifiche)
   vengono depositati in Talamus.
4. Quel materiale diventa schede citate, che arricchiscono il brain per la prossima
   volta.

**Utenti serviti ma non prioritari a 6 mesi:** knowledge worker, ricercatori,
studenti che usano Talamus come second brain classico (alimentazione manuale +
domande citate). Funziona per loro, ma non è il fuoco dei primi 6 mesi.

**Rimandati a dopo i 6 mesi:** sviluppatori terzi che integrano Talamus come backend
di memoria nei propri prodotti (scenario "C dopo"); team con memoria condivisa di
gruppo.

## 3. Posizionamento competitivo

Il panorama della "memoria per agenti" è affollato e converge verso local-first /
open source. Sintesi dei principali:

- **mem0** — cloud-first, API; store ibrido (vettore + grafo a pagamento); ricorda
  *fatti atomici* estratti dalle conversazioni. Opaco e non verificabile.
- **TencentDB Agent Memory** — local, MIT, pipeline a 4 livelli (grezzo → fatti →
  cognizione → profili); zero API esterne. Il più vicino a noi, ma resta una memoria
  di *fatti*, non di conoscenza curata e leggibile.
- **Zep / Graphiti** — knowledge graph **temporale** (bi-temporale), self-hostable;
  ottima gestione delle contraddizioni; ma richiede un database a grafo (pesante).
- **Letta** — memoria a livelli gestita dall'LLM stesso.

**Dove Talamus è unico (in ordine di punta):**
1. **Ontologia auto-emergente** — la memoria si organizza da sola in una mappa di
   concetti, categorie, domini e relazioni. È il differenziatore di punta: nessuno
   offre uno schema concettuale che cresce e si riorganizza da solo.
2. **Provenienza e citazioni** — ogni affermazione punta a una fonte reale; memoria
   verificabile, non "fatti" opachi.
3. **Substrato unico uomo + agenti** — la tua conoscenza è la memoria dell'agente e
   viceversa; nessun concorrente fonde i due mondi.
4. **Local-first, open source, nessun lock-in** — tutto sul tuo computer, dati in
   formato neutro (nessuna dipendenza da Obsidian o dal cloud).
5. **Semplice e leggero** — gira anche su un PC di media potenza. Zep vuole un
   database a grafo, mem0 vuole Qdrant + Postgres o il cloud; **Talamus gira su un
   portatile** (Markdown + cache leggera + LLM via abbonamento o locale). È un
   vantaggio competitivo reale.

## 4. Principi non negoziabili

- **Local-first**: i dati restano sempre sul computer dell'utente.
- **Modello LLM come adattatore a 3 modi**, default auto-rilevato al primo avvio:
  (a) CLI a modello cloud via abbonamento (claude-cli, codex; nessuna chiave API,
  consuma i limiti dell'abbonamento); (b) API cloud con chiave (a consumo); (c)
  modello completamente locale (es. Ollama). L'utente non è mai obbligato a uno.
- **Open source**, core con licenza Apache-2.0.
- **Motore-first / headless**: usabile al 100% senza UI, via CLI / SDK / MCP.
- **Nessun lock-in di archiviazione**: la verità è Markdown standard; Obsidian è solo
  uno dei modi di vedere le note, mai una dipendenza.
- **Provenienza obbligatoria**: ogni affermazione importante ha una fonte.
- **Il grafo/ontologia è un indice, non la verità**: si risponde dai file reali.
- **Semplice e leggero**: deve girare su PC di media potenza.
- **Zero telemetria**.

> Tensione nota: alcune scelte sono ambiziose (ontologia di Livello 2 bi-temporale,
> quattro tipi di sorgente) e vanno tenute compatibili con il principio "leggero".
> Si risolve in architettura facendo girare il lavoro pesante in modo **incrementale
> e in differita**, mai bloccante e mai onnivoro sul PC.

---

# Parte II — Il cuore della conoscenza

## 5. Il dato canonico: la "scheda"

**L'unità atomica è la scheda = un concetto** (stile pagina wiki): focalizzata e
riutilizzabile. Una fonte può generare più schede; più fonti possono arricchire la
stessa scheda. È questo che permette il comportamento "migliora una scheda esistente
/ creane una nuova / scarta".

Una scheda contiene (campi canonici, indipendenti da Obsidian):
- identificatore stabile, titolo, alias;
- categoria/dominio (vedi ontologia), tag;
- riassunto leggibile;
- testo ottimizzato per la ricerca (`retrieval_text`);
- sezioni del corpo (es. idea centrale, uso pratico, esempi, modi di fallire, note
  implementative);
- **collegamenti** ad altre schede/concetti (con ancora, bersaglio, motivo);
- **relazioni** tipizzate (sorgente, tipo, bersaglio, confidenza);
- **fonti** con provenienza completa: percorso del grezzo, percorso del normalizzato,
  locator (es. "pagine 42-48"), hash della fonte, affermazioni supportate;
- confidenza.

**Collegamenti e provenienza esistono come dati strutturati**, indipendenti dalla
sintassi `[[...]]` di Obsidian.

## 6. L'ontologia auto-emergente (il tratto unico)

Invece di organizzare le schede solo con cartelle ed etichette mantenute a mano, il
sistema **costruisce e aggiorna da solo una mappa dei concetti e di come si legano**,
ricavandola dal contenuto. Obiettivo a 6 mesi: **Livello 2 completo**, costruito a
partire dalle fondamenta del Livello 1.

**Mattoni dell'ontologia:** concetti + categorie + domini + relazioni tipizzate
(tutte entità di prima classe nella mappa).

**Come emerge (in sintesi):**
1. In fase di estrazione, oltre alla scheda si segnano i concetti e i legami.
2. Si unificano i doppioni (es. "RAG" e "retrieval augmented generation" → un solo
   concetto).
3. Periodicamente emergono **categorie** e **gerarchie** (è-un, fa-parte-di) dai
   cluster di concetti.
4. I tipi di legame vengono normalizzati in un vocabolario controllato che cresce.
5. Con nuove schede l'ontologia si aggiorna: fonde concetti, promuove i ricorrenti,
   segnala contraddizioni, forma domini, riorganizza lo schema nel tempo.

**Auto-organizzazione con coda di revisione (non bloccante):** le proposte ad alta
confidenza passano da sole; quelle incerte finiscono in una coda di revisione che la
persona svuota quando vuole. Ogni nodo/relazione ha confidenza e provenienza.

**Contraddizioni e tempo — grafo bi-temporale stile Zep/Graphiti:** ogni fatto/
relazione porta **due assi temporali**: *quando era vero nel mondo* e *quando Talamus
l'ha saputo*. Quando un fatto nuovo contraddice uno vecchio, **il vecchio non viene
cancellato**: viene **invalidato** da una certa data e resta nello storico. Così si
sa sempre cosa era vero e quando, e niente va perso. Un modello LLM confronta il
fatto nuovo con quelli simili per rilevare il conflitto.

**Le note non si spostano fisicamente:** l'ontologia è una **mappa-indice sopra** le
schede; i file restano dove sono (git pulito, nessun link da riparare). Coerente con
"il grafo è un indice, non la verità".

## 7. Organizzazione su disco, formati e git

- **Verità = file Markdown standard con intestazione dati** (frontmatter):
  leggibili e modificabili a mano, git-friendly, aperti da qualsiasi editor e da
  Obsidian. Obsidian è solo un lettore.
- **Indici derivati e rigenerabili**: grafo, ricerca, ontologia e cache vivono in
  un'area tecnica gestita (`.talamus/`, con una cache leggera tipo SQLite). Si possono
  cancellare e ricostruire dai file in qualsiasi momento; non sono la verità.
- **Layout:** le schede stanno in cartelle in chiaro e modificabili; materiale
  grezzo, indici, cache e log stanno nell'area gestita `.talamus/`.
- **Git obbligatorio e automatico:** Talamus committa ai checkpoint significativi
  (dopo un ingest, una ricostruzione, una promozione). Gli originali grezzi non
  vengono mai distrutti. I commit non sono mai forzati su rami condivisi.
- **Più memorie:** esiste un **brain globale** (conoscenza trasversale) e **brain
  per-progetto** (es. uno per repo). Un brain di progetto può attingere in lettura al
  globale.

---

# Parte III — Come la conoscenza ENTRA

## 8. La pipeline di ingestione

Catena unica: `materiale grezzo → normalizzazione → estrazione schede → collegamenti
→ resa → indici/grafo/ontologia`.

**Avvio:**
- **Sessioni-agente: automatico** (depositate a fine sessione, poi messe in coda).
- **Sorveglianza cartelle con soglie:** quando il materiale accumulato supera una
  soglia (es. tot pagine o tot MB), l'elaborazione parte da sola, con carichi che
  **non sovraccaricano il PC**.
- **Ingest manuale** sempre disponibile (lanci tu quando vuoi).

La pipeline è **ripristinabile** (i lavori lunghi riprendono dopo un'interruzione),
mostra **avanzamento/stima**, e usa **cache** per non riconvertire materiale
invariato.

## 9. Tipi di sorgente

**Tutte e quattro presenti nella versione a 6 mesi** (in ordine di costruzione, dal
più leggero al più pesante):
1. **Sessioni-agente** — trascritto della chat + codice scritto + modifiche ai file.
   Cuore dello scenario primario. Prima dell'estrazione, una **compressione
   meccanica** ripulisce il rumore di protocollo e i log dei tool (riduce i token da
   far leggere all'estrattore, senza fare giudizi di valore — quello è compito del
   bibliotecario).
2. **Appunti e Markdown/testo** — passaggio semplice con classificazione e
   provenienza.
3. **PDF** — tramite un convertitore di qualità (es. Docling), come adattatore.
4. **Immagini/screenshot** — tramite OCR, con riporto di confidenza.

Formati oltre i 6 mesi: audio, video, web, ecc., aggiungibili come nuovi adattatori.

## 10. Estrazione e fusione delle schede ("il bibliotecario")

L'estrattore è il "bibliotecario": legge il materiale normalizzato e **produce
oggetti-scheda strutturati**, non Markdown libero. Il sistema poi **valida,
deduplica, collega e rende** le schede in modo deterministico. L'LLM propone, il
sistema controlla.

- **Fusione:** quando è chiaro che la nuova conoscenza arricchisce una scheda
  esistente, viene aggiornata da sola (alta confidenza); nei casi dubbi va in coda di
  revisione.
- **Autori delle schede:** sia il bibliotecario (automatico) **sia la persona a
  mano**. Una scheda scritta o corretta a mano in Markdown (anche da Obsidian) viene
  riconosciuta, re-indicizzata e integrata nell'ontologia.

## 11. Qualità, validazione, revisione e curatela

- **Controlli di qualità** prima che qualcosa diventi scheda: provenienza
  obbligatoria, niente collegamenti rotti, controllo qualità della conversione.
  Conversione **best-effort con controlli di qualità** (non si promette perfezione,
  ma non la si tratta come un limite da sbandierare). Materiale scadente o ambiguo
  va in `review/` o `failed/`.
- **Revisione non bloccante:** tutto procede; gli elementi incerti (contraddizioni,
  fusioni dubbie, proposte di ontologia) finiscono in una coda **asincrona e
  facoltativa**. Il loop con gli agenti gira senza conferme in tempo reale.
- **Come si revisiona a 6 mesi** (UI ancora assente): un comando (`talamus review`)
  elenca e fa approvare/scartare; gli item sono **anche file in chiaro**
  apribili e sistemabili a mano. Già pronto per la UI futura.
- **Dimenticare:** di default "dimenticare" = **archiviare/invalidare** (recuperabile,
  coerente col modello temporale); per privacy è possibile la **cancellazione vera**
  di una fonte/scheda ovunque, come operazione esplicita e tracciata.

---

# Parte IV — Come la conoscenza ESCE

## 12. Recupero

**Strategia: mappa-prima → testo di riserva → espansione sui legami.** Si usa
l'ontologia/grafo per trovare i candidati; se non bastano, ricerca testuale (BM25) di
riserva; poi si allarga seguendo i collegamenti validati. Si restituisce un **piccolo
insieme** di candidati (efficienza di token).

**Restituzione a doppia modalità:**
- **Interrogazione diretta di Talamus** (come dalla futura UI) → Talamus **confeziona
  la risposta citata** usando il modello LLM scelto.
- **Dentro un agente** → Talamus fornisce solo le **risorse** (schede + fonti) e
  risponde l'LLM dell'agente, senza doppioni.

## 13. Gli agenti come bibliotecari

Due livelli di accesso, non uno solo:
- **Livello facile — "chiedi e basta":** una domanda, Talamus fa il giro e restituisce
  le schede giuste.
- **Livello potente — "fai il bibliotecario":** strumenti componibili che l'agente
  combina come vuole.

**Strumenti (via MCP) a 6 mesi:**
- **Cerca** — trova le schede candidate.
- **Naviga la mappa** — esplora concetti, legami e "vicini" di una scheda
  nell'ontologia (è ciò che rende l'agente un vero bibliotecario autonomo).
- **Leggi scheda/fonte** — apre il contenuto reale di una scheda e, se serve, della
  fonte originale.
- **Deposita/ricorda** — consegna nuovo materiale (es. la sessione di lavoro).

**Ambito di default per un agente:** scrive nel **brain del progetto corrente** e
legge anche dal **globale**; l'ambito è sovrascrivibile per sessione.

---

# Parte V — Le porte d'accesso

## 14. Riga di comando, libreria e protocollo agenti

**Porte di prima classe a 6 mesi:** CLI (comandi `talamus ...`), SDK Python (la base su
cui poggiano tutte le porte), e **server MCP locale** (espone gli strumenti agli
agenti, sul modello di un OpenMemory). L'**API HTTP locale** arriva dopo (per la UI e
gli integratori terzi).

**Cattura delle sessioni:** **hook di piattaforma** (es. `Stop`/`SessionEnd` di
Claude Code, analogo per Codex) deposita transcript + modifiche in automatico a fine
sessione, senza dipendere dalla buona volontà del modello; **in più** l'agente può
depositare durante la chat con lo strumento MCP. Funziona con qualsiasi client MCP;
testate ufficialmente Claude Code e Codex.

## 15. La UI futura

**Dopo i 6 mesi.** App **locale** che legge lo **stesso store** (file + cache): il
motore resta perfettamente usabile senza. Compiti previsti:
- **Interrogazione conversazionale**: chiedere a Talamus di trovare o modificare una
  nota e avviare un mini-brainstorming guidato per la modifica, oppure farsi trovare
  direttamente la nota.
- **Visualizzare la mappa/ontologia** (concetti, legami, domini).
- **Lettura stile Wikipedia (anteprima all'hover)**: mentre leggi una scheda, ogni
  wikilink inline mostra all'hover un'**anteprima del corpo** della nota collegata,
  così se incontri un concetto che non conosci lo capisci senza perdere il filo (come
  già fa Obsidian). Richiede wikilink inline nel corpo (non solo nella sezione
  "Related"): per questo le schede linkano i concetti alla prima menzione in ogni
  sezione.
- **Curare la coda di revisione** in modo comodo.
- **Scrivere e modificare le schede** (editor integrato, alternativa a Obsidian).
- **Cruscotto e stato** (lavori in corso, statistiche, salute della memoria).

---

# Parte VI — Sotto il cofano

## 16. Adattatori intercambiabili

Tutto ciò che è una scelta strategica vive dietro un'interfaccia stabile e
sostituibile:
- **Convertitori**: testo/sessione (interno), PDF (es. Docling), OCR per immagini.
- **LLM**: a 3 modi (CLI-abbonamento / API-chiave / locale), default auto-rilevato.
- **Ricerca**: BM25 integrato come default; adattatori più avanzati opzionali.
- **Grafo/ontologia**: implementazione locale e leggera.
- **Archiviazione**: Markdown + cache; altri renderer/viste aggiungibili.

## 17. Configurazione

**Zero-config che funziona:** di default l'utente non tocca nulla; adattatori e
manopole restano nascosti finché non li cerca (avanzato **opt-in**). La configurazione
è **versionata e migrabile** tra le versioni.

## 18. Privacy, sicurezza e local-first

- I **dati restano sempre sul computer** dell'utente.
- Quando si usa un modello **cloud**, i contenuti elaborati vengono inviati a quel
  modello: Talamus lo dichiara con un **avviso chiaro**.
- È possibile **marcare fonti o interi brain come sensibili**: quelli usano solo
  modelli locali (o nessun LLM).
- **Zero telemetria**, mai.

## 19. Robustezza operativa

- **Ripresa** dei lavori lunghi dopo un'interruzione; **avanzamento/stima** sempre
  visibili; **cache** anti-riconversione.
- **Registri**: esecuzioni, decisioni, recupero, errori, migrazioni.
- **Concorrenza:** più agenti/sessioni possono usare lo stesso brain. Le **letture
  sono libere**; le **scritture vengono serializzate** (lock/coda leggera) per non
  corrompere la memoria. Leggero, non un sistema distribuito.

---

# Parte VII — Prodotto e percorso

## 20. Pacchettizzazione, installazione e aggiornamenti

- Distribuzione via **pip/pipx** (ecosistema Python): installazione con un comando,
  naturale per l'utente primario.
- **Aggiornamenti** via pipx, con **migrazioni esplicite e mai silenziose**;
  recupero/rollback possibile tramite git e backup.
- Un **installer standalone** per non-tecnici arriva dopo i 6 mesi.

## 21. Licenza e modello open source

- **Core Apache-2.0.** Massima adozione, accettabile per le aziende.
- **Open-core:** UI ed estensioni future **possono** essere commerciali; il motore
  resta open e permissivo.
- Il core **non dipende** da librerie copyleft (GPL/AGPL); convertitori copyleft o
  commerciali esistono solo come **adattatori opzionali documentati**.
- I **pesi dei modelli non vengono mai inclusi**: l'utente installa e accetta le
  licenze dei modelli separatamente.

## 22. Tabella di marcia (entro i 6 mesi e oltre)

Ordine pensato per avere valore usabile presto e rispettare il principio "leggero".

**Traguardo 1 — il loop agente su testo.**
Cattura (hook + MCP) → compilazione (estrazione + fusione) → recupero (mappa-prima) →
CLI + MCP, su **sessioni-agente e appunti/Markdown**. Store Markdown + cache, git
automatico. **Fondamenta di ontologia (Livello 1):** concetti unificati, relazioni
tipizzate, categorie suggerite. È il "leggi → lavora → ricorda" end-to-end.

**Traguardo 2 — più sorgenti.**
Aggiunta di **PDF** e **immagini/OCR** con i controlli di qualità.

**Traguardo 3 — ontologia verso il Livello 2.**
Categorie e domini, modello **bi-temporale**, rilevamento contraddizioni,
riorganizzazioni di schema nel tempo; curatela più ricca.

**Dopo i 6 mesi:** UI locale; API HTTP; sorgenti audio/video/web; memoria di team /
multi-utente; installer standalone; integrazione per sviluppatori terzi ("C").

> Idee più lontane e spiegate nel dettaglio (es. **endpoint MCP remoto autenticato**
> per usare il brain dagli LLM nel browser): vedi
> [evoluzioni future](talamus-future-evolutions.md).

## 23. Criteri di successo e non-obiettivi

**Successo (versione a 6 mesi):**
- Un power-user collega i suoi agenti; gli agenti **leggono** dal brain mentre
  lavorano e **vi depositano** il lavoro.
- Le sessioni e i documenti diventano **schede citate**, organizzate da un'ontologia
  che cresce da sola.
- Tutto **gira su un PC di media potenza**.
- Le risposte sono **citate da file reali**.
- **Nessun lock-in:** le note si aprono e si leggono senza Talamus e senza Obsidian.

**Criteri di accettazione:**
- nessun collegamento rotto nelle schede finali;
- ogni affermazione importante ha una fonte;
- grafo, indice e ontologia sono ricostruibili dai file;
- i lavori interrotti riprendono o falliscono in modo pulito;
- i comandi base non richiedono conoscenza degli adattatori.

**Non-obiettivi (entro i 6 mesi):**
- SaaS / hosting cloud multi-utente;
- sorgenti audio, video, crawling del web;
- memoria di team / multi-utente.

*(La "conversione perfetta garantita" non è elencata come non-obiettivo: la
conversione è best-effort con controlli di qualità, ma non viene sbandierata come
limite.)*

---

## Sintesi della tensione da governare

La visione è ambiziosa (ontologia di Livello 2 bi-temporale, quattro sorgenti) ma il
prodotto deve restare **semplice e leggero**. Questi due fatti non sono in conflitto
se l'architettura rispetta tre regole:
1. il lavoro pesante (estrazione, ontologia) gira **in differita e in modo
   incrementale**, mai bloccante;
2. i default sono **a basso costo** (LLM via abbonamento già installato, cache
   leggera, niente database pesanti);
3. ogni capacità avanzata è **opt-in** e non rallenta il caso comune.
