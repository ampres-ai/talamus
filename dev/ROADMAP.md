# Talamus — Roadmap to Publication

This is the **umbrella plan**: the ordered path that takes Talamus from its current
state to a public launch, and the principles that govern every decision on the way.
It is deliberately hyper-detailed: for several phases this document is enough to
act on directly, with no separate spec→plan. Where a phase still needs a design
conversation with the maintainer, it carries a **🧠 brainstorm** flag and appears
in the *Brainstorm gates* index (§ Part 3).

It complements, and does not replace, the canon:
[CONSTRAINTS](CONSTRAINTS.md) (binding rules), [ARCHITECTURE](ARCHITECTURE.md) (how
it works), [STATE](STATE.md) (what is built/measured/rejected), [PRODUCT](PRODUCT.md)
(the finished-product definition). When this roadmap and the canon disagree, the
canon's governance wins; update both in the same change.

> Language note: this file is in English on purpose — the whole dev canon is
> English, and Phase P0 makes "all code and chrome in English" a hard rule. A
> roadmap that mandates English cannot itself be written in another language.

---

## Part 0 — The strategic spine (the "why" that orders everything)

### 0.1 What Talamus is (decided, not aspirational)

**One brain, two consumers.** Talamus is a single local-first knowledge brain used
*natively* by two consumers at once: the **human** (who curates and reads it) and
the **agent/LLM** (who recalls from it and writes back to it). It is **agent-native
AND human-native from the same core** — not a human wiki with an MCP bolted on.
This is the structural advantage competitors (who added agent access to a
human-first product) cannot easily copy.

### 0.2 The wedge (the one truth that makes someone switch)

Talamus **democratizes powerful agent-memory** for people who already have the
*means* (a capable PC, or one €20 coding-agent subscription) but not the
*infrastructure*. The wedge, in four inseparable parts:

1. **Shared** — the memory you and your agent actually use together, natively.
2. **In your language** — full semantic power without speaking English (notes,
   search and answers in the user's mother tongue; the machine layer stays
   English-canonical under the hood).
3. **Cheap** — answers cost few tokens; the memory does not burn the user's
   subscription limits.
4. **Zero extra setup** — nothing beyond the agent/PC the user already has. No new
   account, no cloud, no embedding infra, no API key required.

**The word to own:** *"the memory your agent already has."* We do not out-feature
the competition on the human-wiki battlefield; we own a category they cannot claim.

### 0.3 The endgame (the victory condition)

The **beloved open-source de-facto standard** for local agent-memory. **Adoption is
the north star.** A technically perfect but unused Talamus is a *failure*. Therefore
**when purity and adoption conflict, adoption wins** — without ever betraying the
free-first constitution below.

### 0.4 The constitution (free-first)

Every decision is gated by one question: **"does it serve the user who has no extra
money or infrastructure?"** The free, local, zero-setup core is **completed first and
made excellent**. Power-features for the user who *can* pay (paid API models,
optional embeddings, etc.) come **after launch** and **may never weaken the free
core**. Talamus charges nothing; it *supports* users who bring their own power.

### 0.5 The five cross-cutting principles (the gate on every PR)

1. **Free-first** — serve the no-extra-cost user first; power-ups never required.
2. **Lightness / runs everywhere** — the software is light; disk space goes to the
   **content** (raw, notes, graphs), not the runtime; **every phase runs on a modest
   PC**; heavy converters (docling/OCR/embeddings) are always **opt-in, never
   mandatory**. A phase that needs a powerful PC is a design bug. *(~60% of the
   target audience does not have strong hardware.)*
3. **Two-corpora law (to be extended + tiered)** — no retrieval/quality change ships
   unless it wins measured ablations on the real corpora; negatives recorded; CI
   floors lock wins. The current corpora (docs 120-case, book 35-query) are
   **too small/generic**: they are being **extended, and a third domain-diverse
   corpus added (P1.5)**, so ablations carry signal, not noise. Crucially,
   benchmarks are **tiered for speed** (see the operating constraint below): the
   dev loop must stay fast.
4. **€0 / local** — no cloud, no per-call API requirement in the free path.
5. **Adoption = north star** — optimize for DX, virality and contributors;
   adoption beats purity when they conflict.

Plus three operating constraints: **solo + AI-agents sprint** (one maintainer +
coding agents, ruthless focus, launch ASAP); **green gate + STATE always current**
(so any agent can resume cold — the antidote to bus-factor = 1 and burnout); and
**tiered benchmarks for speed** — a **FAST tier** (small stratified subsets + the
recall floors) runs in **seconds**, in CI and locally, on **every change**; a
**HEAVY tier** (full corpora, LLM judges, scale) is gated (`TALAMUS_BENCH_HEAVY`) and
run **on-demand only**. Local runs and the dev loop must stay fast — benchmarks may
never steal infinite time on this PC.

### 0.6 The two primary users (precise targeting)

| Archetype | Engine path | Notes |
|---|---|---|
| **A — Local power** | capable PC running **gemma (ollama) locally** | zero subscription; €0; needs the lightest possible local processing |
| **B — One subscription** | ONE **€20/month** coding-agent subscription | driven via the **official CLI = subscription auth** (no API key): Claude (claude-cli), **ChatGPT = codex-cli** (Codex is bundled in the ChatGPT subscription), Gemini (gemini-cli), **Kimi (kimi-cli)**, **opencode** |
| Secondary — Power/API | €1000/month of API credits | post-launch; brings their own paid models; never the primary target |

**Cursor is NOT an engine** — it is an IDE that *consumes* Talamus via MCP. Talamus
plugs into Cursor as a memory server, it does not drive Cursor as an LLM.

### 0.7 What "publication" means (the launch bar)

Launch = the **complete free core**, a **co-launch of both consumers**:
- a **finished human UI** (the moats made visible),
- a **solid agent MCP** (the perfect-MCP pillars),
- **migration import** from llm_wiki (and Obsidian/Notion) to remove the switching wall,
- **zero-setup onboarding** (nothing beyond the agent/PC the user already has),

all **local / €0**, all running on a **modest PC**. Power-features are post-launch.

---

## Part 1 — Pre-launch phases (ordered)

Each phase: **Goal · Why it serves the wedge · Work items · Modules touched · Exit
criteria (incl. a footprint/runs-on-a-modest-PC check) · 🧠 if it needs a brainstorm.**
Phases are mostly sequential for a solo sprint; dependencies are noted. Each phase
ends green (`python dev.py`) and updates STATE.md.

### P0 — Clean-code & English-ization (the starting point)

**Goal:** a codebase that is entirely English, free of dead code, and immediately
comprehensible and maintainable by anyone who takes over — the precondition for the
OSS/contributor endgame.

**Why it serves the wedge:** the endgame is a *beloved, contributed-to* OSS project.
Contributors cannot read a half-Italian codebase. This also de-risks bus-factor = 1.

**Work items:**
- **English everywhere in `src/`:** comments, docstrings, AND user-facing **chrome**
  strings (CLI output, UI labels). Today these are heavily **Italian** (verified:
  `cli.py`, `ask.py`, `ingest.py`, `mcp_server.py`, the whole `ui/`). Convert all of
  it to English. *(The NOTES stay in the user's language — that is the wedge. Only
  the chrome and the code go English. Chrome i18n is a post-launch feature, § Part 2.)*
- **Dead-code sweep:** find and remove unused code (suspects to verify: `demo.py`
  vs the demo service, `services/library.py` — barely wired, legacy BM25/in-memory
  search paths superseded by the persistent index, any orphan helpers). Use coverage
  + import-graph + manual review; do not delete provenance/migration paths that are
  intentionally dormant.
- **Split oversized files:** `cli.py` is **1839 lines**; split by command group
  (e.g., `cli/` package: ingest, ask, brains, ontology, jobs, review, system). Keep
  the public `main()` entry stable.
- **Clean-code pass:** consistent naming, single-responsibility modules, clear
  boundaries; no clever-but-opaque code; every public function has an English
  docstring saying *what it does, how to use it, what it depends on*.

**Modules touched:** all of `src/talamus/` (sweep), especially `cli.py` → `cli/`,
`ask.py`, `ingest.py`, `mcp_server.py`, `ui/*`, the `services/*` chrome.

**Exit criteria:** a grep finds no Italian in `src/` comments/docstrings/chrome; a
dead-code report is clean (or every kept exception is justified); `cli.py` is split;
`python dev.py` green; a fresh reader can navigate the tree. Footprint unchanged.

### P1 — Foundations & the service spine

**Goal:** one clean seam between core logic and interfaces, and stop advertising
capabilities that do not exist.

**Why:** the co-launch (human UI + agent MCP) is only affordable solo if both ride
**one spine**. Build the spine once, serve both consumers.

**Work items:**
- **Finish the services seam:** make it a rule — **interfaces (CLI/UI/MCP) call ONLY
  `services/`, never the core directly.** CLI was fully migrated; **MCP is now fully
  migrated too** (all read+write tools route through `services/`, incl. four new
  service ops: `query.brain_overview`/`note_history_view`, `ingestion.ingest_raw_text`,
  `review.propose_review_note`). `services/library.py` is now **wired** (the MCP
  `sources` tool reads via `get_library_note`). **Remaining: UI is ~10%** (only the
  readiness Home) — migrate its action views (settings, ingest with the
  cost-estimate/consent/jobs, review) onto the services. *(UI = codex's track.)*
- **Honesty fix (done):** `config.py`/`doctor` advertised `pdf_converter="docling"`
  and `ocr=ollama/glm-ocr` but neither is wired (PDF = pypdf, no OCR). Honest
  defaults now ship (`pypdf`/`none`/`none`), `doctor` shows `ocr: none (planned)`,
  and `docs/configuration.md` is corrected. Real wiring stays P3.
- **Canon alignment (done for CLI/MCP):** `ARCHITECTURE.md` now states the seam rule,
  the `cli/` package split, and MCP-on-services; revisit when the UI migration lands.

**Modules touched:** `services/*`, `ui/app.py`, `ui/views.py`, `mcp_server.py`,
`cli/lifecycle.py`, `config.py`, `services/diagnostics.py`.

**Exit criteria:** every CLI/UI/MCP action goes through a service; no interface
imports a core module directly for business logic; `doctor`/`config` claim only what
exists; gate green; UI ingest now has the same cost-estimate/consent/jobs as the CLI.

### P1.5 — Benchmark corpora & speed (the foundation under the two-corpora law)

**Goal:** make the ablations that gate the retrieval/quality work (P2, P3, P5)
**trustworthy**, while keeping every local and CI run **fast**.

**Why:** the two-corpora law only protects quality if the corpora carry signal — and
today they are small/generic (docs 120-case, book 35-query; one enriched corpus, so
enrich/ontology are validated only on the book). A solo sprint also dies if tests are
slow, so speed is a first-class requirement, not an afterthought.

**Work items:**
- **Extend the existing corpora:** more and less-generic judged queries on the docs
  and book corpora; **expand the negatives set** (so honest-refusal becomes
  statistically meaningful, not a 1-question delta).
- **Add a third corpus** 🧠: domain-diverse, to fight overfitting. Decide its nature
  (brainstorm): a **public judged retrieval set** (fast, reproducible, breadth) vs a
  **third local enriched brain** (full workflow + anti-overfit, but needs ingestion +
  hand judging) — possibly one in each tier.
- **Lock the tiering:** a **FAST tier** (stratified subsets + the recall floors) that
  runs in **seconds** in CI and locally on every change; a **HEAVY tier** (full sets,
  LLM judges, scale) gated by `TALAMUS_BENCH_HEAVY`, run on-demand. Audit current
  bench runtimes; cut anything in the fast tier that is not fast.

**Modules touched:** `benchmarks/`, `tests/test_talamus_recall_floor.py`, `corpus.py`,
`eval.py`, the eval-set files (local book eval stays local/copyright-safe).

**Exit criteria:** the fast tier runs in **seconds** (measured) on this PC and in CI;
a third corpus exists; ablations on the extended corpora show **stable** signal across
runs; heavy runs are gated and documented as on-demand; gate green.

**Round 1 — DONE** (see [dev/specs/2026-06-24-p1.5-benchmark-corpora-design.md](specs/2026-06-24-p1.5-benchmark-corpora-design.md)
+ plan): the **garden corpus** (third local enriched brain) exists — 18 frozen CC0
factual articles across 6 unrelated domains, a deterministic `build_garden_corpus`,
33 judged cases, a FAST recall floor (recall@5 0.95, runs in ~0.7 s) and a HEAVY
`TALAMUS_BENCH_HEAVY` test that drives the real extract→enrich→ontology pipeline on
it. Docs negatives expanded 10→25. FAST/HEAVY tiers measured (~2.8 s combined) and
documented in `benchmarks/README.md`. Gate green (528 tests, 5 skipped).
**Round 2 (deferred):** a frozen post-enrich snapshot of the garden in the FAST tier;
a public judged retrieval set (Wikipedia/Gutenberg).

### P2 — Engines = real subscriptions (the heart of the wedge)

**Goal:** Talamus works perfectly on the engine the user *already has* (local gemma
or one €20 subscription), and squeezes the **highest quality out of the cheapest
model + effort**, while gracefully surviving exhausted limits.

**Why:** "cheap" and "zero extra setup" are two of the four wedge parts. Today the
promise "works with your subscription" is **partly false** (Kimi/opencode not wired;
Cursor wrongly implied).

**Tiering DONE (2026-07-02, branch `feat/p2-tiering`):** every LLM call site now
resolves its model+effort through `talamus.routing.EngineRouter`, per a `TaskClass`
(ten classes; spec:
[dev/specs/2026-07-01-p2-model-effort-tiering-design.md](specs/2026-07-01-p2-model-effort-tiering-design.md)).
Bulk/mechanical tasks default to the **economy** tier (claude haiku, codex
gpt-5.4-mini/low, gemini flash); the answer the user reads (`ask_answer`), session
capture and source verification default to **quality**. Config gains `task_tiers` +
`provider_models` overrides; `StaticRouter` pins one engine for tests/overrides;
tiering stays WITHIN the single configured provider (no cross-provider routing this
round). Flags smoke-tested live (claude `--model`, codex `-m` +
`model_reasoning_effort` incl. `xhigh` on gpt-5.5; gemini `-m`, no effort). Savings
evidence: [dev/research/2026-07-p2-tiering-savings.md](research/2026-07-p2-tiering-savings.md).
Also fixed en route: engine failures now surface the real CLI error (stdout, e.g. a
401) instead of a blind exit code. **Remaining P2 work** (separate slices):
usage-limit detection + graceful fallback + the hard per-call timeout;
kimi-cli/opencode adapters; anthropic-api effort.

**Work items:**
- **Subscription-CLI coverage:** keep claude-cli, codex-cli (= ChatGPT), gemini-cli,
  ollama; **add `kimi-cli` and `opencode`** as engine adapters (verify each exposes a
  non-interactive completion and authenticates via the user's subscription). Remove
  any implication that Cursor is an engine.
- **Direct-subscription research** 🧠: the **official CLIs already use subscription
  auth, not API keys** — that is the safe, primary "use your subscription" path.
  Investigate whether a *direct* connection (à la `openclaw`/`hermes`, using the
  login session token without a CLI) is worth it for providers lacking a usable CLI —
  **flagging the ToS risk and fragility honestly**; default to the CLI path.
  `openai-compatible` (API key + base URL) is the **secondary** path for the
  power/API user (it costs per token), not the primary target.
- **Model + effort tiering/routing** 🧠 *(flagship lever):* introduce **per-task
  model + effort selection** so each operation uses the cheapest model that is good
  enough. Define task classes — *extraction, ask-routing, query-expansion,
  ask-answer, verify/judge, enrich, consolidate, ontology-naming, session-remember* —
  and assign each a **tier** (cheap/fast vs strong) and an **effort** level
  (e.g., gemini flash vs pro; claude haiku/sonnet low-effort vs opus high-effort;
  codex effort levels; ollama small vs large). Config: sensible cost-minimizing
  defaults + per-task overrides; consider auto-tiering. **Goal: top quality while
  consuming as little of the subscription's limits as possible.**
- **Usage-limit detection + graceful handling** + **hard timeout:** detect each
  engine's "rate/usage-limit exhausted" error signature and handle it — pause the
  job *resumably*, fall back to a cheaper model or local ollama, and tell the user
  clearly (with retry-after). Add a **hard per-call timeout in the adapter** (the
  gemini-on-Windows hang and the slow-local-model case; RS8 measured ~12.5% of gemma
  generations > 90 s). Extend the hostile-model battery for the new shapes.

**Modules touched:** `adapters/llm.py` (new providers, options, timeout,
limit-detection, tiering hooks), `config.py` (per-task tiering config),
`services/engines.py`, a new engine-routing module, every LLM call site (pass a
task-tier), `tests/test_talamus_hostile_models.py`.

**Exit criteria:** each named subscription works end-to-end (measured); per-task
tiering is configurable with default token savings *measured* vs a flat strong model;
an exhausted limit yields a graceful, resumable outcome (never a crash/hang); a hung
engine is abandoned within the timeout; gate + hostile battery green. Runs on a
modest PC (no local heavy model required when using a subscription).

### P3 — Ingestion: quality AND lightness

**Goal:** the brain is only as good as what is extracted — and ingestion must run on
a modest PC by default. Fix the open chunking question and make heavy parsing opt-in.

**Why:** garbage-in → garbage-memory; and the lightness principle (60% modest
hardware). The current ingest "is not super light."

**Work items:**
- **Chunking** 🧠 *(open question):* `split_chunks` cuts at paragraph boundaries, so a
  concept spanning a boundary can be split and lost (STATE open front #9). Add an
  **overlap window** and/or **semantic chunking** so boundary concepts survive, while
  staying **deterministic** (resume depends on it). Measure the effect on ingest
  quality.
- **Extraction front-end (opt-in, heavy):** wire **docling / MarkItDown / OCR** as
  optional extras to cover more formats (pptx, xlsx, images) — this resolves the
  "docling declared but unwired" gap from P1. The **default path stays light**
  (pypdf + stdlib); heavy converters never load unless the user opts in.
- **Lightness of the default path:** measure and bound the ingest footprint; ensure
  the default extraction + indexing run on a modest PC without large local models.
- **Prune heavy raw files post-extraction** 🧠 *(lightness feature, tension to
  resolve):* offer to **delete the heavy original binary** after extraction, keeping
  the **normalized text + source hash**. ⚠️ This trades against the **verifiability
  moat**: `provenance_status`/`verify` re-extract the RAW to compare; with the binary
  gone, verify degrades to *note ↔ normalized* (not *note ↔ original*). Make it
  **configurable** (the disk-poor user opts in) and define the degraded "verify-lite"
  mode explicitly. Brainstorm the UX + the exact guarantee kept.
- **Extraction quality per tier:** cheap models compress specifics (STATE RS2.5) —
  measure per tier and let extraction pick a stronger tier when it matters.
- **Ingest-quality benchmark:** a metric for "did the notes capture the source"
  (coverage, correct interlinks, no lost boundary concepts).

**Modules touched:** `ingest.py`, `sources.py`, `normalize.py`, `extract.py`, a new
chunking module, optional `docling`/`markitdown` front-end, `paths.py` (raw-retention
policy), `correct.py` (verify-lite mode), `benchmarks/` (ingest-quality).

**Exit criteria:** boundary concepts survive (measured); default ingest footprint
measured and modest-PC-safe; heavy converters are opt-in; raw-prune available with a
documented verify-lite guarantee; ingest-quality benchmark committed; gate green.

### P4 — Multi-brain & federation (engineered properly)

**Goal:** the central brain is fed by *all* projects and reads from *any* archive;
initializing a brain in a folder ingests that folder — even a codebase.

**Why:** "one shared brain" at the personal scale = a central hub of everything the
user does, plus per-project brains; this is core to the thesis, and currently
under-engineered.

**Work items:**
- **Central fed by all:** every project brain feeds the central hub (promote /
  federate); the central **reads from any registered archive**. Make the federated
  index robust and incremental.
- **`init` ingests the folder** 🧠: initializing a brain in any folder **ingests that
  folder's content**, including a **codebase / code repository** (route through the
  existing `scan` with secret redaction + code digests). Seamless on `init`/`setup`,
  with the dry-run cost preview and consent (lightness: must run on a modest PC).
- **Scope/promote/federation hardening:** project-only / central-only /
  project+central / all policies tested at scale; `brains promote` and the
  `[central]` federation markers verified end-to-end.

**Modules touched:** `registry.py`, `scope.py`, `federation.py`, `scan.py`, `cli`
setup/init, `services/brains.py`, possibly `services/library.py` (a unified
"all brains / all sources" surface).

**Exit criteria:** `init` on a folder (incl. a real code repo) produces a usable
brain; the central aggregates all projects; cross-brain ask/search works; federation
is incremental and modest-PC-safe; gate green.

### P5 — Token & cost benchmarks (the wedge, measured and shown)

**Goal:** turn "fewer tokens / doesn't burn your limits" from a claim into measured,
*user-visible* fact.

**Why:** token/cost efficiency is a **sales promise**, not an internal detail — the
target user runs gemma on a laptop or has finite subscription limits.

**Work items:**
- **Benchmarks:** tokens-per-answer; quality on a small/local model; **per-task
  subscription-limit consumption** by tier; latency and timeout rates per engine.
  Extend `benchmarks/profiler` and the token-efficiency module; add a cost/limit
  profiler.
- **Show the cost to the user:** surface "this answer cost ~X tokens" (and, where
  known, "~Y% of your limit") in `ask --trace` and the UI.
- Validate P2's tiering with these numbers (the cheap tier must keep quality).

**Modules touched:** `benchmarks/`, `ask.py`/`cli.py`/UI (cost display).

**Exit criteria:** a committed token/cost benchmark with per-tier numbers; a
user-facing cost display; tiering savings proven without quality loss; gate green.

### P6 — The perfect MCP (brainstorm + engineering) 🧠

**Goal:** the best agent-memory MCP that exists — on all four pillars at once, plus
a *magical* conversation→memory loop.

**Why:** the agent half of the co-launch; the "perfect MCP" the maintainer asked for.

**Pillars (all required):**
1. **Context-frugality** — the agent retrieves the *minimum* it needs to reason,
   never a dump; Talamus protects the agent's context window and tokens (the wedge).
2. **Zero-config reliability** — one command; works with *any* agent/IDE
   (Claude Code, Codex, Cursor, …); never hangs (hard timeout); degrades gracefully.
3. **Rich protocol on the moats** — the agent does more than read/write: **as-of**
   (how it was at a date), **verify** (is this still true?), see-stale,
   **propose → review**. The agent becomes a first-class *curator*, not just a reader.
4. **Weak-model ergonomics** — self-describing tools, safe defaults, outputs even a
   small/local model uses correctly first time (the hostile-model ethos for tool use).

**The magic loop** 🧠: evaluate whether the current capture path — hook →
`remember_session` → extract notes from transcript+diff behind the "worth-remembering"
gate — is **natural and effective or clunky**. **Measure the quality** of notes
extracted from real conversations. Target: the agent *just remembers*, and what it
remembers is good — it must feel like magic, not configuration.

**Modules touched:** `mcp_server.py`, `session.py`, `ingest.remember_session`,
`scripts/talamus-session-hook.py`, services.

**Exit criteria:** MCP installs in one command across agents; uses the cheap tier;
the conversation→note loop is measured + judged "magic"; the protocol exposes
as-of/verify/propose; the agent never blows its context window using Talamus.

### P7 — Finish the human UI + make the moats VISIBLE

**Goal:** the UI stops being "functional Flet" and becomes lovable — and it
*shows* the superpowers nobody currently sees.

**Why:** the human half of the co-launch; the biggest gap vs the competition is UX,
and the moats are invisible today.

**PIVOT (2026-06-26) — the UI becomes a local WEB workbench (React).** After a viral +
IDE-workbench brainstorm, the foundation moved from Flet to a **React + Vite + TS SPA**
served by a thin **FastAPI bridge over `services/`** (P1's seam pays off), opened as a
**native window via pywebview** (plug-and-play preserved; downloadable desktop-icon
binary at release via PyInstaller; CLI/MCP stay zero-setup — the GUI is an optional
`[ui]` extra). Identity = **"Aurora"** (electric indigo + cyan); the **living graph is
the hero**. The Flet UI (codex's work) keeps running and its views/copy/tests are the
**blueprint**; it is retired only at parity. The graph layout reuses `ui/physics.py`
server-side. Spec + plan:
[dev/specs/2026-06-26-p7-web-workbench-design.md](specs/2026-06-26-p7-web-workbench-design.md),
[dev/plans/2026-06-26-p7-web-workbench-skeleton.md](plans/2026-06-26-p7-web-workbench-skeleton.md).
**Workbench BUILT + on `main`** (2026-06-27, gate green 585). Beyond the skeleton:
- **All 9 views ported** to React on the services seam — Home, Ask (cited answer),
  Graph, Library, Import (preview→consent→run, cost gate), Ontology Lab, Review
  (the verifiability moat), Brains, System — plus a right-side Inspector (note body,
  metadata behind a "details" toggle).
- **Brain switching like Obsidian vaults**: `GET/POST /api/active` swaps the active
  brain at runtime (mutable root); the sidebar shows the current vault; Brains lets you
  open a registered brain, open any folder, or **create a new brain** (`/api/brains/init`).
- **Aesthetic + IDE pass** (used the design skills): Aurora design-token system, VS Code
  chrome (activity-bar indicator, closeable tabs, labeled nav with **@phosphor-icons**),
  real scrolling, staggered CSS motion, focus rings.
- **Graph**: organic radial **d3-force** constellation (client-side layout; the bridge
  ships nodes+edges only, fast at any size), degree-based hierarchy, faint curved edges,
  hub labels, hover-trace, fit-to-view.

**Remaining (deferred — not blocking the return to engine/product):** Flet retirement at
parity; packaging (PyInstaller desktop-icon binary); a bundled offline display font;
command palette (⌘K); WCAG audit; surfacing the as-of/verify moats in the new views.
**2026-06-27 decision (Giovanni): the UI is in good shape — focus returns to the ENGINE
and the real product** (P2 engines/tiering, P3 ingestion quality+lightness, the invisible
moats). The "Anchor design" below stays the IA/copy reference.

**Anchor design:** build on **codex's UI-completion design**
(`.superpowers/specs/2026-06-15-talamus-ui-completion-design.md`) — a strong,
services-first, task-first plan (Home/Ask/Library/Import/Graph/Review/Ontology/
Brains/System, a universal right-side inspector, an Obsidian-grade graph,
accessibility, desktop packaging) that already designs the moats as visible. Note
that `services/library.py` is its already-built **Library** backend (not dead code).
**Three amendments before adopting it** (it predates the 2026-06-18 inquisition and
is human-UI-first): (1) add the **lightness/footprint** gate — the app + the Flet
bundle must run on a modest PC (principle #2; the design is silent on it); (2)
reconcile with the post-inquisition spine — co-launch **agent-native** framing, the
wedge, **token-cost shown as a promise**, model/effort tiering; (3) **standalone
desktop distribution is a PRODUCT-scope decision** → maintainer approval (PRODUCT.md),
as the design itself flags.

**Work items:**
- Complete the services migration (from P1); polish the eleven views.
- **Surface the moats:** the timeline/**as-of** ("see your brain at a past date"), a
  **verify** panel ("what may be stale / wrong vs its source"), **ontology insights**
  (clusters, surprising links, gaps — the equivalent of competitors' graph insights),
  the **language power** (full semantic memory in your tongue), and the **token cost**
  per answer (from P5).
- Visual quality pass; maintainer's visual verdict ("worth its stars").

**Modules touched:** `ui/*` (app, views, graph, physics, theme), services.

**Exit criteria:** UI fully on services; the four moats are visible and demoable;
maintainer visual sign-off; runs on a modest PC.

### P8 — CLI aesthetics

**Goal:** the CLI — a primary surface for the developer/agent user — is beautiful and
legible.

**Work items:** consistent, English, portable-color output; a polished dashboard and
`status`/`doctor`; readable progress for jobs; no visual noise.

**Modules touched:** `cli/` (post-split), `log.py`, `progress.py`.

**Exit criteria:** the CLI chrome is polished, English, and portable across terminals.

### P9 — Migration import ("magic") 🧠

**Goal:** lower the switching wall — moving to Talamus does not cost the user what
they built elsewhere.

**Why:** import is a **go-to-market wedge**, not a feature: it grows Talamus by
subtraction from competitors.

**Work items:** import from **llm_wiki (primary)**, **Obsidian**, **Notion**.
Brainstorm the scope: what transfers 1:1, and what gets **upgraded** with the moats
(history/as-of, verify, emergent ontology) on import. The primary importer targets
llm_wiki's on-disk format.

**Modules touched:** new importers (under `services/`), `ingest`, `store`, `linking`.

**Exit criteria:** importing an llm_wiki/Obsidian vault yields a working Talamus
brain with the moats applied; gate green.

### P10 — Zero-setup onboarding

**Goal:** zero-to-first-answer in minutes, with nothing beyond the agent/PC the user
already has.

**Work items:** `talamus setup` detects the agent/PC, **picks the cheap engine tier
by default**, and in one command produces a working shared brain + installed MCP +
session hook. The whole flow runs on a modest PC.

**Modules touched:** `cli` setup, `services/engines.py`, `services/integrations.py`,
`services/readiness.py`, `demo`.

**Exit criteria:** a new user on a modest PC, with only their existing agent, reaches
a cited first answer in minutes; setup never requires a paid API key.

### P11 — Launch readiness

**Goal:** ship.

**Work items:** a **clean `pip install` on a clean machine** (verified); packaging /
installer (at minimum a clean pip + extras; consider a Flet desktop bundle to match
the competition's installer); **100k-note scale** check (search latency, footprint);
a **viral demo** ("your agent remembers, free, in your language, in one command");
the **"own a word" messaging**; user docs; the release checklist.

**Exit criteria:** cold install works on Linux/macOS/Windows; 100k notes usable on a
modest PC; demo + messaging ready; PRODUCT.md launch bars met; **launch**.

---

## Part 2 — Post-launch / R&D (power-ups; never weaken the free core)

- **Power-features for the paying user:** paid API models and **optional embeddings**
  (opt-in, additive, never required for the free path).
- **Diffusion-models brainstorm** 🧠: do nascent diffusion models help *retrieval in
  memory*? Evaluate strictly through the free-first + lightness + two-corpora lens —
  the bar is "does it help the **local/€0/modest-PC** user," not just "is it novel."
- **Chrome i18n** (wedge-aligned): localize the CLI/UI chrome so non-English users get
  their language end-to-end (notes are already in their tongue).
- **Open to contributors:** open well-bounded, high-value areas first — engine
  adapters, competitor importers, file formats — where coordination overhead is low.
- **Bigger benchmarks (heavy tier):** building on the corpora extended in P1.5, grow
  toward a large multi-domain judged set and run the slowest, most thorough
  measurements on-demand — a real **head-to-head vs llm_wiki** on the same corpus
  (wiki+ask), full-scale 100k runs, and the multilingual steelman on the ASK path.
  These stay in the gated heavy tier; the fast tier (P1.5) keeps the dev loop quick.

---

## Part 3 — Brainstorm gates (pointers, decisions owed to the maintainer)

Each is described in full in its phase; this is the at-a-glance checklist of
conversations we owe each other before building:

- **P1.5** — the third corpus (public judged set vs a third enriched local brain).
- **P2** — direct-subscription connection (CLI vs openclaw/hermes-style; ToS).
- **P2** — model + effort tiering policy (defaults + per-task overrides).
- **P3** — chunking (overlap vs semantic) + prune-raw-vs-verify trade-off.
- **P6** — the perfect-MCP design (4 pillars) + the magic conversation→memory loop.
- **P7** — how to make the moats visible in the UI.
- **P9** — migration import scope (what transfers vs what gets upgraded).
- **P11** — launch messaging ("own a word").
- **Part 2** — the diffusion-models bet.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Bus-factor = 1 / burnout (solo sprint) | green gate + STATE always current (any agent resumes cold); land an early *lovable* milestone to sustain momentum |
| Weak launch (sprint cuts too much) | the launch bar (§0.7) is fixed; cut scope, not the free-core quality |
| Direct-subscription ToS risk | default to official CLIs; treat openclaw/hermes-style as research, flagged |
| Prune-raw vs verifiability | configurable; define the verify-lite guarantee explicitly (P3 🧠) |
| Heavy ingestion on weak PCs | light default path; heavy converters opt-in; footprint is an exit criterion everywhere |
| Scope creep (the vision is large) | free-core launch first; everything else is Part 2 |
| Chasing llm_wiki on its turf | own a word; win on shared/agent-native/language/cost, not feature count |

---

## How this document is used

The roadmap is the **umbrella**. Phases that are fully specified here can be executed
directly (their own spec→plan optional). Phases with a 🧠 flag get a dedicated
brainstorm → spec → plan before execution. We start at **P0** and proceed in order,
keeping the gate green and STATE current at every step. This file is updated as
phases complete (move detail into STATE.md's build history; keep the forward plan
here).

## Current-state baseline (verified audit, 2026-06-18, `main` @ 8cf5c94)

What already exists and is solid (so the roadmap builds, not rebuilds): the
three-channel no-embeddings retrieval (+ RS8 adaptive trigram beating BM25 on
SciFact), the routed cited `ask` (book hit@8 0.972), the emergent ontology + domains,
bitemporal time, active verify, the resumable chunked ingest, the full CLI (~40
commands) delegating to a new **services layer** (18 modules, `ServiceResult`,
`readiness`), the MCP (8 read + 6 write tools), the Flet UI (11 views, readiness Home),
the SDK and the session hook, ~115 test files, and a serious benchmark suite. Known
gaps this roadmap closes: heavily-Italian code/chrome (P0), unwired docling/OCR (P1/P3),
UI/MCP not fully on the services spine (P1/P7), engine coverage + tiering + limits
(P2), ingestion lightness + chunking (P3), and the invisible moats (P7).
