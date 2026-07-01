# P2 — Model + Effort Tiering — Design

**Status:** approved by Giovanni (2026-07-01), pending spec self-review sign-off.
**Roadmap:** [dev/ROADMAP.md](../ROADMAP.md) — P2, "Model + effort tiering/routing (flagship
lever)".

## Goal

Every LLM call in Talamus should use the **cheapest model+effort that is good enough for
that specific task**, instead of one flat engine setting for the whole brain. Bulk/
mechanical work (extraction, routing, naming) should default to the cheap/fast tier;
quality-critical work (the answer the user reads, verification against a source) should
default to the strong tier. This is measured, configurable, and provider-agnostic.

## Why

Talamus's wedge is "cheap, zero extra setup, works on your subscription." Today every
call — from bulk book ingestion to the final answer — uses the *same* model, so cost and
quality are not actually optimized per task. This is the flagship lever named in the
roadmap.

## Core abstraction: two axes, resolved per provider

A **task class** is a named point in the pipeline that makes exactly one LLM call. Each
task carries an **intent**: `{tier, effort}`.

- **`tier`**: `"economy"` | `"quality"` — *which model* a provider uses.
- **`effort`**: `"low"` | `"high"` — *how hard* that model should think (reasoning
  effort / thinking budget), where the provider exposes such a knob.

Each **provider** (claude-cli, codex-cli, gemini-cli, ollama, anthropic-api) owns its own
**descriptor**: a mapping from `(tier, effort)` to its own concrete model name + whatever
CLI flag expresses effort, if any. Task classes never know provider-specific model names;
providers never know about task classes. Where a provider doesn't expose an effort knob
(ollama has none; gemini-cli's is unverified), `effort` is accepted and silently ignored —
tiering degrades to "tier only" for that provider rather than failing.

**Scope note (removes a real ambiguity):** tiering operates *within* the single provider
already configured for the brain (`config.llm_provider`) — it changes which model/effort
that one provider uses per task, never which provider. A brain has one subscription
active at a time today, so cross-provider routing (e.g. send bulk extraction to a free
local ollama while the paid subscription handles the final answer) is a plausible future
evolution but explicitly **not** built here — see "Out of scope."

## Task classes (mapped from the real call sites in the codebase today)

| Task class | Call site (today) | Default intent | Why |
|---|---|---|---|
| `extraction` | `extract.py::extract_notes` (via `ingest.py::_compile_package`) | economy / low | Bulk, mechanical, structured JSON output; the highest-volume call (one per chunk of every ingested document) |
| `session_remember` | `ingest.py::remember_session` → same extractor, different intent | quality / low | An agent's own captured insight — smaller volume, worth a better model than bulk book ingestion |
| `ask_routing` | `ask.py::_route_member_titles` (area + domain routing) | economy / low | Picks IDs off a list; a cheap model is enough |
| `query_expansion` | `ask.py::_expand_query`; `smartsearch.py::expand_query`/`expand_query_multi` | economy / low | Keyword rewriting, not reasoning |
| `ask_answer` | `ask.py::answer_from_items` | quality / high | The text the user actually reads and judges Talamus by |
| `verify` | `correct.py::verify_note` | quality / low | Judging a note against its source needs real comprehension, but is a single short call |
| `enrich` | `enrich.py::enrich_notes` | economy / low | Batch enrichment across many notes |
| `consolidate` | `consolidate.py::_detect_groups` | economy / low | Duplicate-detection over a listing |
| `ontology_naming` | `ontology_lab.py` (relation-type naming) | economy / low | Naming a handful of clusters |
| `overview_naming` | `domains.py::build_overview` + `build_overview_tree` (flat/batched/tree domain naming) | economy / low | **Discovered during mapping** — not in the roadmap's original task list, but a real, distinct call site (domain/cluster naming for the brain overview) with its own cost profile. Flagging this explicitly rather than silently folding it into `ontology_naming` (a different, unrelated call site). |

Defaults live in code (`talamus/routing.py`), not config — an uninitialized brain gets
sensible cost-minimizing behavior with zero setup, matching the free-first constitution.

## Per-provider descriptors — what's verified vs. what needs a smoke-test

Two providers (`codex-cli`, `gemini-cli`) already have an unused `-m <model>` hook in the
adapter, with comments hinting this exact intent ("e.g. a mini model for fast bulk
ingest" / "e.g. a flash model") — this design wires up what was already anticipated.
Being honest about what's confirmed vs. what needs verification against the installed
CLI version before merging:

| Provider | Tier → model | Effort mechanism | Confidence |
|---|---|---|---|
| `claude-cli` | NOT wired today (hardcoded `["claude", "-p"]`, no model flag passed) | — | `--model <alias>` needs a smoke-test at implementation time (Task 1) |
| `codex-cli` | Already wired via `-m` | `-c model_reasoning_effort=low\|high` (config override) | Smoke-test at implementation time |
| `gemini-cli` | Already wired via `-m` | No known simple flag | Assume unsupported (effort no-ops) unless the smoke-test finds one |
| `ollama` | Model name only (already supported) | None — ollama has no effort concept | N/A, always no-ops |
| `anthropic-api` | Model name only | Out of scope this round (would need `max_tokens`/thinking-budget changes to the Messages API call) | Documented gap, not implemented |

The exact default model string per tier (e.g. which Claude alias means "economy") is a
config default seeded at implementation time from the installed CLI's supported aliases —
not hardcoded to a specific dated model ID that will go stale.

## Components

**`talamus/routing.py`** (new, core module — alongside `ask.py`/`ingest.py`, not under
`services/`, since core call sites are core modules):
- `TaskClass` — a `str` enum of the ten classes above.
- `TaskIntent(tier, effort)` — a frozen dataclass.
- `DEFAULT_INTENTS: dict[TaskClass, TaskIntent]` — the table above, in code.
- `EngineRouter` — built once per call (from a `TalamusConfig`, mirroring today's
  `build_provider(config.llm_provider, config.llm_model)` per-call construction — no
  long-lived global state, so config changes take effect immediately). Exposes
  `for_task(task: TaskClass) -> LLMProvider`, memoized per `(provider, model, effort)`
  within one router instance so two tasks resolving to the same engine share one object.
- `StaticRouter(provider: LLMProvider)` — a router that returns the same fixed provider
  for every task regardless of tier/effort. This is the test/back-compat shim: dozens of
  existing tests inject a single fake `LLMProvider`; wrapping it in `StaticRouter(fake)`
  is a one-line change instead of rewriting every fake to be task-aware. Only the new
  tiering-specific tests need per-task fake routers.

**`adapters/llm.py`** (extended, not replaced):
- Each provider descriptor becomes a per-provider `dict[(tier, effort), model]`-style
  mapping (or equivalent), consulted by a new `build_provider_for_task(provider_name,
  tier, effort) -> LLMProvider`. `build_provider(provider, model)` (today's single-model
  builder, keyed on `config.llm_model`) is untouched and keeps meaning exactly what it
  means today: an explicit, untiered model forced by the caller (e.g. a future `talamus
  ask --model X` override, or any caller not yet converted to the router). The two
  fields don't compete: **tiered call sites never read `config.llm_model`**; they read
  `provider_models` instead (see Config below). This is an unambiguous 2-step resolution
  for tiered sites — (1) intent: `task_tiers[task]` override else `DEFAULT_INTENTS[task]`;
  (2) model: `provider_models[provider][tier]` override else the provider's built-in
  tier→model default — with no third "explicit override" step in the tiered path.
- Provider constructors (`ClaudeCliProvider`, `CodexCliProvider`, `GeminiCliProvider`)
  gain an optional `effort: str | None` constructor arg; only append the effort flag when
  the smoke-test confirms the provider supports it, else ignore it silently (never raise
  for an unsupported effort — that would break the "just works" promise).

**Config (`TalamusConfig`)** — two new optional fields, both empty-by-default (an
uninitialized brain uses 100% code defaults):
- `task_tiers: dict[str, dict[str, str]]` — per-task override, e.g.
  `{"extraction": {"tier": "quality"}}`.
- `provider_models: dict[str, dict[str, str]]` — per-provider tier→model override, e.g.
  `{"claude-cli": {"economy": "haiku", "quality": "opus"}}`, for a user who wants a
  specific model pinned regardless of what the CLI's default alias resolves to.

## Call-site conversion (the mechanical part)

Every function that makes an LLM call directly (a "task leaf") switches from accepting
`llm: LLMProvider` to accepting `router: EngineRouter`, and resolves its own engine via
`router.for_task(TaskClass.X)` right before calling `.complete(...)`. Higher-level
orchestrators that call several leaves with *different* intents (the clearest example:
`ask.py::answer_question` calls routing, then expansion, then the answer — three
different tiers in one logical "ask") also switch to accepting `router` and pass it down,
letting each sub-call resolve its own tier. This is why the router (not a single
resolved `llm`) is the right shape — a single high-level operation can legitimately span
multiple tiers.

**Real files affected** (mapped from the actual `.complete()` call sites, not guessed):
`ask.py`, `ingest.py` (+ the `_compile_package`/`extract_notes` task-threading below),
`extract.py`, `consolidate.py`, `correct.py`, `enrich.py`, `domains.py`,
`ontology_lab.py`, `smartsearch.py` — plus every caller that currently builds a single
`llm`/`llm_factory` and passes it in: `cli/_common.py` (`_provider_for` →
`_router_for`), `cli/pipeline.py`, `cli/query.py`, `cli/groups.py`, `mcp_server.py`, and
the `services/*.py` wrappers that build a provider today (`services/ask.py`,
`services/ingestion.py`, `services/scan.py`, `services/enrich.py`,
`services/verification.py`, `services/consolidation.py`).

**The one real fork:** `remember_session` and `ingest_file`/`ingest_text` both funnel
through `_compile_package` → `extract_notes`, but want *different* intents
(`session_remember` vs `extraction`). `_compile_package`/`extract_notes` gain a
`task: TaskClass = TaskClass.EXTRACTION` parameter so `remember_session` can pass
`TaskClass.SESSION_REMEMBER` while the bulk-ingest callers use the default.

This is a broad but mechanical refactor (signature changes + one resolve call each),
fully covered by the existing test suite via `StaticRouter`, executed function-group by
function-group with the gate green after each group.

## Testing

- **Adapter tests**: each provider builds the right CLI args for each `(tier, effort)`
  combination (fake runner, asserting on captured `args`); unsupported effort is a silent
  no-op, never an exception.
- **Router tests**: `EngineRouter.for_task` resolves the code default for each
  `TaskClass`; a `task_tiers` config override wins; a `provider_models` override wins;
  memoization returns the same object for two tasks sharing a resolved engine.
- **Call-site tests**: existing tests keep passing via `StaticRouter(fake_llm)` (a
  mechanical find-replace); a handful of new tests confirm specific functions request the
  expected `TaskClass` (e.g. `answer_question` requests `ask_routing` then
  `query_expansion` then `ask_answer`, in order, using a recording fake router).
- Extend `tests/test_talamus_hostile_models.py` for the new provider constructor args.
- Full gate (`python dev.py`) green throughout; no real LLM calls in the gate (same
  discipline as the existing ask/ingest tests).

## Out of scope for this round (separate P2 slices, not mixed in here)

- Usage-limit detection, graceful fallback, and the hard per-call timeout — a distinct,
  already-scoped P2 work item; keeping it separate keeps this refactor's diff reviewable.
- `anthropic-api` effort/thinking-budget support.
- Adding `kimi-cli` / `opencode` as new engines (a different P2 slice: subscription
  coverage).
- Auto-tiering / budget-driven routing (a possible future evolution once tiers exist and
  are measured; today's tiers are static config, not adaptive).

## Exit criteria

- All ten task classes resolve through `EngineRouter` with the defaults above; every real
  call site listed above is converted (no leftover single-`llm` task leaves).
- `task_tiers` and `provider_models` config overrides work and are documented.
- Token/cost savings from the new defaults vs. today's flat setting are *measured* on at
  least one real ingestion (bulk extraction at `economy` vs. today's flat tier) —
  matching the roadmap's exit bar ("default token savings measured").
- Gate green (`python dev.py`); hostile-model battery extended and green.
- No behavior change for a user who sets no overrides beyond "cheaper defaults, same or
  better answer quality" (ask_answer stays at the strong tier).
