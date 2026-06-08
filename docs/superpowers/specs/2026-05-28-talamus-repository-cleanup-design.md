# Talamus Repository Cleanup Design

Date: 2026-05-28

## Status

Approved direction for the cleanup/refactor phase. This document is written as
the source of truth for the next implementation plan.

The product name is now **Talamus**.

## Purpose

Convert the repository from a personal `FDE Brain` prototype into a clean
open-source Talamus codebase.

The repository should stop looking like a local Obsidian workspace with an
attached experiment folder. After this cleanup, a new contributor should see a
small Python package, focused tests, product docs, agent guidance, and no
tracked personal knowledge artifacts.

## Non-Goals

- Do not implement Docling, OCR, LLM extraction, scheduling, or UI.
- Do not redesign the retrieval architecture.
- Do not rename the physical Windows workspace folder from inside the active
  Codex/Claude session.
- Do not preserve old personal knowledge files in the active repository.
- Do not keep Graphify as a core or legacy dependency.

## Naming Decision

Canonical product name: `Talamus`.

Code and packaging names:

- Python package: `talamus`
- CLI command: `talamus`
- PyPI/project name: `talamus`
- Config filename: `talamus.json`
- Default project status text: `talamus project status ok`
- Agent skill name: `talamus-knowledge`

No compatibility alias for `brain` is required in this phase. The current code
is still pre-release, so a direct rename is cheaper than maintaining two names.

## Physical Workspace Rename

The current workspace path is:

```text
c:\Users\Giovanni Crapuzzi\Documents\Formazione\FDE Brain
```

The desired local folder name is:

```text
c:\Users\Giovanni Crapuzzi\Documents\Formazione\Talamus
```

This rename should happen only after the internal refactor is committed and all
tools using the old directory are closed. The implementation plan should provide
manual post-commit instructions, not run a workspace move command.

## Repository Shape After Cleanup

Keep:

```text
.gitattributes
.gitignore
AGENTS.md
CLAUDE.md
LICENSE
README.md
docs/
pyproject.toml
skills/talamus-knowledge/SKILL.md
src/talamus/
tests/test_talamus_*.py
```

Remove from tracked repository:

```text
AI Space/
FDE Brain/
tools/fde_brain/
skills/brain-knowledge/
tests/test_ask.py
tests/test_chapters.py
tests/test_classify.py
tests/test_distill.py
tests/test_distill_local.py
tests/test_distill_v3.py
tests/test_graphify.py
tests/test_ingest.py
tests/test_layout.py
tests/test_length.py
tests/test_normalize.py
tests/test_normalize_v2.py
tests/test_ocr.py
tests/test_paths.py
tests/test_pdf_render.py
tests/test_preflight.py
tests/test_registry.py
tests/test_rerun_local_distill.py
tests/test_run_log.py
tests/test_validate_obsidian.py
tests/test_validate_workspace.py
```

The legacy test fixture under `tests/fixtures/` should be removed if it is only
used by legacy `tools/fde_brain` tests.

Generated caches such as `__pycache__/` should be removed locally and ignored by
git. They should not appear in the final status.

## Files To Rename

Package files:

```text
src/brain/ -> src/talamus/
```

Tests:

```text
tests/test_brain_ask.py -> tests/test_talamus_ask.py
tests/test_brain_cli.py -> tests/test_talamus_cli.py
tests/test_brain_graph.py -> tests/test_talamus_graph.py
tests/test_brain_models.py -> tests/test_talamus_models.py
tests/test_brain_obsidian_renderer.py -> tests/test_talamus_obsidian_renderer.py
tests/test_brain_paths_config.py -> tests/test_talamus_paths_config.py
tests/test_brain_search.py -> tests/test_talamus_search.py
```

Skill:

```text
skills/brain-knowledge/ -> skills/talamus-knowledge/
```

## Reference Updates

Update all active references from `brain` to `talamus` where they describe the
product, package, CLI, config, tests, or skill.

Examples:

- `from brain...` becomes `from talamus...`
- `python -m brain.cli` becomes `python -m talamus.cli`
- `brain init` becomes `talamus init`
- `brain.json` becomes `talamus.json`
- `BrainPaths` can either become `TalamusPaths` or remain temporarily if the
  implementation plan chooses minimal API churn. Preferred result is
  `TalamusPaths`, `TalamusConfig`, and `TalamusCliTests`.
- `Brain Knowledge Skill` becomes `Talamus Knowledge Skill`

Historical docs may mention the old name only when explicitly describing the
cleanup history. User-facing docs should use Talamus.

## Documentation Updates

`AGENTS.md` should describe the repository as Talamus, not the old personal
workspace.

`CLAUDE.md` should be rewritten for Talamus development. It should not mention
the old scheduled ingestion role, `FDE Brain`, or `AI Space`.

Create a concise `README.md` if it does not exist. It should explain:

- what Talamus is
- current status: early local-first knowledge compiler foundation
- install/test commands for local development
- beginner CLI examples using `talamus`
- graph is an index, not source truth
- Apache-2.0 license

Update `docs/agent-tool-calling.md` to use Talamus commands and terminology.

The existing Superpowers design and plan files can remain as development
history, but the cleanup implementation plan should update the current
foundation plan only if needed for naming consistency. Old Graphify-centered
docs should be removed or explicitly archived only if they remain tracked after
legacy folder deletion.

## Git And Local-State Rules

Do not stage or commit local-state content changes:

```text
.claude/
AI Space/graph/brain/graphify-out/
AI Space/graph/brain/.stale
```

Deleting tracked files under `FDE Brain/.obsidian/` is intentional when the
whole legacy `FDE Brain/` directory is removed. Do not stage modifications to
those files as local UI state; stage only their deletion as part of removing the
legacy tracked folder.

After deleting `AI Space/` and `FDE Brain/`, these paths should no longer matter
for the tracked repository, but the implementation should still avoid staging
untracked local residues accidentally.

If the current plan checkbox file
`docs/superpowers/plans/2026-05-27-core-graph-first-foundation.md` has
uncommitted progress marks, either commit it separately before the cleanup or
leave it unstaged. Do not mix it into the rename/removal commit unless the user
explicitly asks.

## Test Strategy

The cleanup is successful when:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

passes with only Talamus tests.

CLI smoke test:

```powershell
$tmp = Join-Path $env:TEMP "talamus-cleanup-smoke"
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
$env:PYTHONPATH="src"
python -m talamus.cli init --root $tmp
python -m talamus.cli status --root $tmp
python -m talamus.cli doctor --root $tmp
```

Expected:

- all commands exit `0`
- `$tmp/talamus.json` exists
- `$tmp/knowledge/notes` exists
- output uses `talamus`, not `brain`

Repository hygiene checks:

```powershell
git ls-files | rg "^(AI Space|FDE Brain|tools/fde_brain|src/brain|skills/brain-knowledge)"
rg -n "FDE Brain|AI Space|Graphify|graphify|Dual Graph|tools\\.fde_brain|from brain|python -m brain|brain init|brain\\.json" .
```

Expected:

- no active tracked legacy paths
- no active product docs or code using old names
- historical mentions only where intentionally retained in Superpowers history

## Risk And Mitigation

Risk: deleting legacy folders removes reference material that could help future
conversion work.

Mitigation: the reference remains recoverable from git history. The active repo
should prioritize clarity over carrying old prototype data.

Risk: renaming `brain` to `talamus` breaks imports or console entrypoints.

Mitigation: perform the rename through tests first, update import paths
mechanically, and run the full test suite plus CLI smoke commands.

Risk: local untracked artifacts get staged accidentally.

Mitigation: check `git status --short --untracked-files=all` before commit and
stage explicit paths only.

## Acceptance Criteria

- Package imports use `talamus`.
- CLI command is `talamus`.
- Config file is `talamus.json`.
- Tests are named `test_talamus_*`.
- Legacy tracked folders are removed.
- Product docs and agent protocol use Talamus terminology.
- Talamus test suite passes.
- The repository can be physically renamed to `Talamus` after tools are closed.
