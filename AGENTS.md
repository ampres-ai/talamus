# Agent Workspace Instructions

This repository is **Talamus**: an open-source, local-first knowledge compiler
with time, meaning and verifiability — a second brain for humans and a memory
for AI agents, powered only by the LLM the user already has.

## Read this first (in order)

1. [dev/CONSTRAINTS.md](dev/CONSTRAINTS.md) — the binding rules and WHY.
2. [dev/ARCHITECTURE.md](dev/ARCHITECTURE.md) — how every part works, module
   by module. Read the relevant section before touching a subsystem.
3. [dev/STATE.md](dev/STATE.md) — what is built, the measured numbers, what
   was REJECTED with data (do not redo dead experiments), the open queue.
4. [dev/PRODUCT.md](dev/PRODUCT.md) — the final product definition and the
   numeric bar for "finished".
5. [dev/ROADMAP.md](dev/ROADMAP.md) — **the forward plan and how to continue.**
   Rewritten 2026-07-02 as a legacy document for successor models: it carries the
   strategy (§0–§4) and the ordered, acceptance-tested execution phases to launch
   (§5), plus how to delegate to codex (§6). If you are here to advance the
   project, this is your map — read §0 every session.

User-facing docs live in `docs/` (the mkdocs site) — update them in the same
change that alters public behavior. Historical specs/plans are archived
outside the repo; git history holds everything.

## The golden rules (full rationale in dev/CONSTRAINTS.md)

- Quality gate: **`python dev.py`** (ruff + format + mypy + unittest).
  ALL GREEN before any commit. Works on every OS.
- Product code in `src/talamus/`, tests in `tests/test_talamus_*.py`,
  CLI name `talamus`, config `talamus.json`.
- **No embeddings.** Semantic power is bought at ingest (by construction) and
  via the user's LLM at ask time.
- **OS-agnostic and LLM-agnostic**, development to product. Weak models are
  first-class: anything consuming LLM output degrades gracefully
  (see `tests/test_talamus_hostile_models.py` — extend it when adding any
  new LLM-consuming code path).
- Markdown notes = human truth; cache JSON = machine truth; graph/indexes/
  overview/federation = derived, always rebuildable, never source truth.
- No bulk LLM spend without dry-run estimate + explicit `--yes`.
- Provenance always; corrections are proposed to review, never auto-applied;
  invalidate, never delete.
- Retrieval/quality changes ship only after winning measured ablations on
  BOTH corpora (`retrieval_lab.py` + `talamus eval`); add a CI floor for every
  win; record negative results in STATE.md.
- Tests stay hermetic: `tests/__init__.py` redirects `TALAMUS_HOME` to a
  throwaway directory — never weaken that.
- Never commit `.claude/`, generated caches, `.talamus/`, or content derived
  from copyrighted sources (local eval-sets stay local).

## Known traps (learned the hard way — they will bite you too)

- `write_note` / `write_note_json` MERGE with the existing note (equal
  confidence keeps the OLD prose): to replace content use
  `overwrite_note_json`.
- `merge_notes` keeps higher-confidence prose but must UNION search fields;
  retrieval_text union is already handled — keep it that way.
- Model JSON is hostile by default: parse with `strict=False`, salvage
  balanced objects from truncated answers, isolate batches so one bad answer
  cannot sink the rest. Never let a parser swallow errors silently into an
  empty-but-plausible result.
- Big-document ingest chunks deterministically (resume depends on it); chunk
  files are `.md` (extracted text), never the source binary extension.
- `source_hash` is computed over extracted TEXT: comparisons must re-extract,
  never hash file bytes (line endings and binary formats differ across OS).
- Job records left in `running` by a killed process are adopted on resume —
  preserve that behavior when touching `jobs.py`.
- Environment notes for THIS dev machine (Windows): long git commits through
  a bash-emulation tool can hang — prefer the native shell for git; shell
  heredocs can mangle backslashes in generated Python — write temp script
  files instead. On other OSes use the native equivalents; never encode
  OS-specific commands into product code or docs.
- Engine CLIs are agents themselves: codex runs with a read-only sandbox,
  gemini with `--approval-mode plan` — never loosen those flags.
- Codex writes files via PowerShell can re-encode UTF-8 as cp1252 (mojibake:
  `—` becomes `â€”`) — after any codex write job, grep the touched files for
  `â€` before committing.

## Documentation governance (how to change the canon)

The four `dev/` documents are the canon. Quality bar: English; dense but
complete sentences; every number sourced from a measured run; no dates in
filenames (research reports and benchmarks are the exception: they are
immutable lab notebooks).

| Document | When to update | Who approves |
|---|---|---|
| `dev/STATE.md` | every milestone: move numbers into the dashboard, append the build-history row, record rejected experiments, prune the queue | the agent doing the work, in the same commit |
| `dev/ARCHITECTURE.md` | same change that alters how a subsystem works | the agent doing the work, in the same commit |
| `dev/CONSTRAINTS.md` | a constraint is added, changed or dropped | **maintainer approval required** before commit |
| `dev/PRODUCT.md` | scope, thesis, bars or out-of-scope change (pivots) | **maintainer approval required** before commit |
| `AGENTS.md` (this file) | new trap discovered, reading order changes, governance changes | the agent, in the same commit; governance table changes need maintainer approval |

Rules for edits: update, don't append-only (no "edit logs" inside documents —
git history is the log); keep each document's single responsibility (product
questions belong in PRODUCT.md, not ARCHITECTURE.md); when superseding a
claim, replace it — never leave two versions of the truth; if you find the
docs contradicting the code, the code is the truth and the doc gets fixed in
the same commit.
