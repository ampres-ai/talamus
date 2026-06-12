# RS2 — Precisione e potenza estreme (log di ricerca, 2026-06)

Seconda campagna di ricerca scientifica sul motore (dopo
[2026-06-recall-research.md](2026-06-recall-research.md)). Vincoli invariati:
niente embeddings, core stdlib, indici derivati, ogni cambio passa dalle
ablazioni — solo i vincitori entrano in produzione.

**Novità di metodo: due corpora reali.** Oltre al corpus docs (74 note,
120 casi, in CI), un libro vero da 500 pagine ("AI Engineering", 243 note
estratte con gemini-3.1-flash-lite) con un eval-set di 42 casi che resta
locale (il contenuto deriva da un libro con copyright). Tutto ciò che vince
deve vincere su entrambi.

## Baseline del libro (percorso search di produzione, k=5)

| metrica | valore |
|---|---|
| recall@5 | 0.722 |
| MRR | 0.641 |
| hit-rate | 0.806 |
| rifiuto negativi | **0.000** |

Per categoria (recall): direct 0.958 · **direct-en 1.000** · cross 0.625 ·
**vague 0.375 · vague-en 0.250**.

Tre fatti:
1. **Il cross-lingua by-construction è validato su un secondo corpus
   indipendente**: domande inglesi su note a titolo italiano = recall 1.0
   (alias canonici inglesi + retrieval_text bilingue, decisi all'ingest).
2. **Il gap vago è confermato e isolato**: tutti e 7 i casi mancati sono
   parafrasi vaghe ("il modello si inventa le cose" → Allucinazione).
3. **Il motore non rifiuta mai**: su carbonara/TCP/mondiali risponde sempre
   qualcosa.

## Esperimenti (tutti deterministici, zero LLM)

### E1 — Espansione ontologica nel bundle (RS2.1): NESSUN LIFT

Scoperta preliminare: a `limit` pieno l'espansione 1-salto in
`build_context_bundle` è un **no-op** (i seed riempiono già il taglio).
Ablazione vera: scambiare seed di ricerca con vicini tipizzati
(`make_bundle_variant`, 5 varianti, libro a 48% archi tipizzati):

| variante | recall@5 | MRR |
|---|---|---|
| solo seed | 0.667 | 0.602 |
| 3 seed + espansione typed-first | 0.667 | 0.602 |
| 3 seed + solo archi tipizzati | 0.653 | 0.602 |
| 3 seed + espansione piatta | 0.667 | 0.602 |
| 4 seed + espansione | 0.653 | 0.602 |

**Verdetto: il valore retrieval dell'ontologia NON è nello scoring** —
coerente con la bocciatura della propagazione in RS1 (-2pt). Il suo valore
misurato sta altrove: clustering dei domini (i 25 domini del libro nascono
dai 368 archi), routing gerarchico, navigazione (neighbors/UI/MCP).

### E2 — Tokenizzazione dei composti con trattino: BOCCIATA

Diagnosi vera: il canale lessicale è cieco ai composti
("Mixture-of-Experts" = un token; la query "mixture of experts" non matcha
mai). Misura dello split: libro identico (il canale trigram già fa da
ponte sui trattini), docs leggermente peggio (-0.005 recall, -0.013 MRR: i
composti esatti lì aiutano). **Respinta: l'architettura a 3 canali copre già
il caso.**

### E3 — Rifiuto dei negativi (RS2.6): tre iterazioni, nessun separatore

1. *Canali accesi* (lex==0 → rifiuta): FALLITA — l'overlap di vocabolario
   inganna ("cluster" in una domanda kubernetes è una parola vera del libro:
   lex_top 8.5).
2. *Copertura dei termini informativi* (df-driven): FALLITA — le function
   words inglesi sono fuori vocabolario in un corpus a prosa italiana e
   affondano le domande EN legittime ("what is mixture of experts?" → 0.0).
3. *Copertura dei soli termini di contenuto* (stoplist grammaticale IT+EN):
   negativi a 0.33–0.67, ma i positivi vaghi scendono fino a 0.0 —
   **distribuzioni sovrapposte, nessuna soglia pulita**.

**Conclusione onesta: il rifiuto duro a livello search non è affidabile senza
semantica.** Il guardrail di livello risposta però funziona già (verificato
in the wild: domanda RLHF/DPO → l'ask ha rifiutato onestamente invece di
allucinare). Direzione candidata: la copertura-contenuti come **segnale
soft** ("il brain non sembra coprire questo argomento") passato all'ask, non
come filtro duro.

### E4 — PRF, pseudo-relevance feedback (RS2.4): BOCCIATO

3 varianti (fb_docs/pesi) su entrambi i corpora: il gap vago NON si muove
(libro vague 0.188 fisso), MRR peggiora su docs (-0.035), cross-source
peggiora. Modalità di fallimento classica: quando la prima passata sbaglia
completamente, i documenti di feedback sono sbagliati e l'espansione
amplifica l'errore.

**Diagnosi finale del gap vago: è semantico puro** — "si inventa le cose"
non condivide alcun token (né trigramma utile) con "Allucinazione". Nessun
trucco lessicale a query-time lo colma.

## Prossime ipotesi (in ordine)

1. **Vocabolario dei sintomi all'ingest (RS2.4-bis)**: l'estrattore aggiunge
   al retrieval_text le formulazioni con cui un utente PORREBBE il problema
   ("si inventa le cose, sbaglia i fatti, risponde cose false" per
   Allucinazione). Ponte semantico by-construction: costo una tantum
   all'ingest, zero a query, stessa filosofia degli alias canonici. Da
   misurare con re-ingest A/B di un sottoinsieme.
2. **Percorso ask completo (RS2.2)**: l'ask ha già l'espansione query via
   LLM che la search non ha — il gap vago potrebbe essere già parzialmente
   coperto lì. Da misurare end-to-end (routing LLM: ~2 chiamate/caso,
   stimare prima). Include il fix della selezione intra-dominio (caso
   RLHF/DPO: hit #1 della search globale non letto dall'ask instradato).
3. **Consolidazione duplicati (RS2.3)**: il libro ha duplicati reali
   (Fine-tuning/Finetuning, 3× Prompt Engineering, 2× Allucinazione) che
   diluiscono il ranking; misurare prima/dopo.
4. **Granularità estrazione vs modello (RS2.5)**: flash-lite comprime i
   dettagli (niente nota RLHF/DPO dedicata).

## Strumentazione aggiunta (in repo)

- `retrieval_lab.make_bundle_variant` / `run_bundle_ablations` — varianti
  del percorso bundle (seed vs espansione ontologica).
- `retrieval_lab.rejection_report` — copertura dei termini di contenuto +
  sweep delle soglie di rifiuto.
- L'eval-set del libro e il brain restano locali; il harness per rifarli da
  un proprio PDF è tutto in repo (`talamus ingest` + `talamus eval --cases`).
