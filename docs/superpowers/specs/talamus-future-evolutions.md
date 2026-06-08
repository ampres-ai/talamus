# Talamus — Evoluzioni Future Possibili

Idee deliberatamente **fuori scope adesso**, ma da ricordare. Ognuna è spiegata a
sufficienza per ricordarne il senso anche fra mesi.

---

## 1. Endpoint MCP remoto autenticato (per gli LLM da browser)

**Problema che risolve.** Oggi Talamus espone l'MCP in **locale** (stdio, e in opzione
`127.0.0.1`). Perfetto per i client **locali** — Claude Code, Claude Desktop, Cursor —
cioè app che girano sulla tua macchina e quindi possono raggiungere `localhost`. Ma gli
LLM usati **dal browser** (claude.ai dentro Chrome, chatgpt.com) **non** possono
raggiungere il tuo `localhost`: i loro "connettori" MCP sono **remoti**, cioè è il
**cloud** di Anthropic/OpenAI che chiama un **URL pubblico HTTPS**, non il browser che
apre una porta sulla tua macchina. Quindi da una scheda del browser non si arriva al
brain locale.

**Soluzione.** Esporre il server MCP di Talamus su un **endpoint pubblico HTTPS**
(FastMCP supporta già il transport HTTP/SSE: è lo **stesso codice**, solo un trasporto
diverso). Due modi:
- **Tunnel** dalla macchina locale (cloudflared / ngrok): il brain resta sul tuo PC, ma
  diventa raggiungibile tramite un URL pubblico (anche temporaneo). Preferibile.
- **Host** dedicato: più stabile, ma sposti i dati fuori dalla tua macchina.

**Perché è fuori scope ora (i compromessi, da ricordare).**
- Rompe il principio **local-first**: apri un pezzo del tuo brain su internet.
- **Sicurezza**: un endpoint pubblico va protetto sul serio. Senza autenticazione,
  chiunque trovi l'URL legge (o peggio scrive) la tua memoria.
- Più setup, più superficie d'attacco, e una scelta di privacy esplicita da fare.

**Come farlo BENE, quando lo faremo.**
- **Autenticazione obbligatoria** (token / OAuth); niente endpoint aperti.
- **Sola lettura** di default (l'LLM da browser legge, non scrive nel brain).
- Possibilità di esporre **un solo brain o un sottoinsieme**, non tutto.
- Preferire il **tunnel** all'host, per tenere i dati sulla macchina.
- Spiegare chiaramente all'utente il compromesso privacy prima di attivarlo.

**In una frase.** Client desktop e agenti locali = gratis e local-first (già fatto);
browser = possibile **solo** esponendo un endpoint remoto autenticato, con i relativi
rischi. Quando il valore lo giustificherà, si fa — con auth e sola-lettura.

---

## 2. Instradamento graph-aware del recupero (ranking ibrido + valutazione)

**Problema.** Oggi il recupero instrada per **parole chiave** (sovrapposizione di
termini) + BM25 di riserva, con un'espansione conservativa via ontologia. Affidabile,
ma non sfrutta davvero le relazioni per trovare note che le parole mancano.

**Cosa abbiamo imparato (stress test, giugno 2026).** I tentativi naive falliscono:
- espansione "riempi gli slot avanzati" (v1): innocua, ma in un brain denso non scatta
  mai perché le parole riempiono già il limite di candidati;
- boost additivo dai vicini (v2): **peggiora** — i nodi-hub (molti vicini) annegano i
  match keyword deboli ma corretti, e spingono fuori risultati giusti.

**Come farlo bene.** Serve un **ranking ibrido vero**, guidato da un **set di
valutazione** (es. recall@k su query con risposte note): combinare segnale keyword +
grafo con **normalizzazione per il grado** del nodo (gli hub non devono dominare), e
*misurare* invece di indovinare. Va affrontato insieme al **Livello 2** dell'ontologia.

**Stato:** mantenuta la v1 sicura (mai peggiore del keyword); il vero graph-routing è
rimandato a quando ci sarà un set di valutazione.
