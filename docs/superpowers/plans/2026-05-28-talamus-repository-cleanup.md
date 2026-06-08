# Talamus Repository Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the product from `brain` to `Talamus`, remove legacy personal-workspace artifacts, and leave a clean open-source Python package with focused tests and docs.

**Architecture:** Perform a direct pre-release rename from `src/brain` to `src/talamus` with no compatibility alias. Remove the tracked prototype folders (`AI Space/`, `FDE Brain/`, `tools/fde_brain/`) and their tests, then rewrite active docs around Talamus. Keep Superpowers history as historical context, but exclude it from active product hygiene checks.

**Tech Stack:** Python 3.13 standard library, `unittest`, setuptools/`pyproject.toml`, Markdown docs, Apache-2.0.

---

## Operating Rules

- Do not rename the physical Windows workspace folder during implementation.
- Do not run `git commit` automatically. The user wants to commit manually.
- Use focused staging suggestions at checkpoints, but leave the actual commit to the user.
- Do not stage `.claude/`.
- Do not stage untracked `AI Space/graph/brain/graphify-out/`.
- Deleting tracked `FDE Brain/.obsidian/*` is allowed only as part of deleting the entire tracked legacy `FDE Brain/` folder.
- Preserve the uncommitted progress marks in `docs/superpowers/plans/2026-05-27-core-graph-first-foundation.md` unless the user explicitly asks to stage them.

## File Structure

Create or keep:

- `src/talamus/__init__.py`
- `src/talamus/ask.py`
- `src/talamus/cli.py`
- `src/talamus/config.py`
- `src/talamus/graph.py`
- `src/talamus/linking.py`
- `src/talamus/models.py`
- `src/talamus/paths.py`
- `src/talamus/search.py`
- `src/talamus/storage/__init__.py`
- `src/talamus/storage/obsidian.py`
- `tests/test_talamus_ask.py`
- `tests/test_talamus_cli.py`
- `tests/test_talamus_graph.py`
- `tests/test_talamus_models.py`
- `tests/test_talamus_obsidian_renderer.py`
- `tests/test_talamus_paths_config.py`
- `tests/test_talamus_search.py`
- `skills/talamus-knowledge/SKILL.md`
- `README.md`
- `docs/agent-tool-calling.md`
- `AGENTS.md`
- `CLAUDE.md`
- `pyproject.toml`
- `LICENSE`
- `.gitignore`
- `.gitattributes`

Remove from tracked repo:

- `src/brain/`
- `skills/brain-knowledge/`
- `AI Space/`
- `FDE Brain/`
- `tools/fde_brain/`
- `tests/test_ask.py`
- `tests/test_chapters.py`
- `tests/test_classify.py`
- `tests/test_distill.py`
- `tests/test_distill_local.py`
- `tests/test_distill_v3.py`
- `tests/test_graphify.py`
- `tests/test_ingest.py`
- `tests/test_layout.py`
- `tests/test_length.py`
- `tests/test_normalize.py`
- `tests/test_normalize_v2.py`
- `tests/test_ocr.py`
- `tests/test_paths.py`
- `tests/test_pdf_render.py`
- `tests/test_preflight.py`
- `tests/test_registry.py`
- `tests/test_rerun_local_distill.py`
- `tests/test_run_log.py`
- `tests/test_validate_obsidian.py`
- `tests/test_validate_workspace.py`
- `tests/fixtures/generate_test_book.py`
- `requirements.txt`

---

### Task 1: Preflight And Dirty-State Guard

**Files:**
- Modify: none

- [ ] **Step 1: Inspect current branch and dirty files**

Run:

```powershell
git branch --show-current
git status --short --untracked-files=all
```

Expected:

```text
codex/local-first-llm-wiki
```

Allowed dirty files before cleanup starts:

```text
docs/superpowers/specs/2026-05-28-talamus-repository-cleanup-design.md
docs/superpowers/plans/2026-05-27-core-graph-first-foundation.md
AI Space/graph/brain/.stale
FDE Brain/.obsidian/graph.json
FDE Brain/.obsidian/workspace.json
AI Space/graph/brain/graphify-out/
```

If any other dirty files exist, stop and report them before modifying the repo.

- [ ] **Step 2: Verify foundation tests still pass before rename**

Run:

```powershell
$env:PYTHONPATH="src"
python -m unittest tests.test_brain_paths_config tests.test_brain_cli tests.test_brain_models tests.test_brain_obsidian_renderer tests.test_brain_graph tests.test_brain_search tests.test_brain_ask -v
```

Expected: PASS.

- [ ] **Step 3: Manual checkpoint for current docs**

Do not run `git commit` automatically.

Tell the user these docs are uncommitted and should be committed or intentionally left unstaged before the cleanup commit:

```text
docs/superpowers/specs/2026-05-28-talamus-repository-cleanup-design.md
docs/superpowers/plans/2026-05-28-talamus-repository-cleanup.md
docs/superpowers/plans/2026-05-27-core-graph-first-foundation.md
```

Suggested user-run commit if they want to checkpoint planning docs first:

```powershell
git add docs/superpowers/specs/2026-05-28-talamus-repository-cleanup-design.md docs/superpowers/plans/2026-05-28-talamus-repository-cleanup.md
git commit -m "docs(plan): add talamus repository cleanup plan"
```

---

### Task 2: Rename Tests To Talamus First

**Files:**
- Rename: `tests/test_brain_ask.py` -> `tests/test_talamus_ask.py`
- Rename: `tests/test_brain_cli.py` -> `tests/test_talamus_cli.py`
- Rename: `tests/test_brain_graph.py` -> `tests/test_talamus_graph.py`
- Rename: `tests/test_brain_models.py` -> `tests/test_talamus_models.py`
- Rename: `tests/test_brain_obsidian_renderer.py` -> `tests/test_talamus_obsidian_renderer.py`
- Rename: `tests/test_brain_paths_config.py` -> `tests/test_talamus_paths_config.py`
- Rename: `tests/test_brain_search.py` -> `tests/test_talamus_search.py`

- [ ] **Step 1: Rename test files**

Run:

```powershell
git mv tests/test_brain_ask.py tests/test_talamus_ask.py
git mv tests/test_brain_cli.py tests/test_talamus_cli.py
git mv tests/test_brain_graph.py tests/test_talamus_graph.py
git mv tests/test_brain_models.py tests/test_talamus_models.py
git mv tests/test_brain_obsidian_renderer.py tests/test_talamus_obsidian_renderer.py
git mv tests/test_brain_paths_config.py tests/test_talamus_paths_config.py
git mv tests/test_brain_search.py tests/test_talamus_search.py
```

- [ ] **Step 2: Rewrite test imports, class names, expected config path, and CLI strings**

Run this PowerShell rewrite:

```powershell
$files = Get-ChildItem -LiteralPath tests -Filter 'test_talamus_*.py' -File
foreach ($file in $files) {
  $text = Get-Content -Raw -LiteralPath $file.FullName
  $text = $text.Replace('from brain.', 'from talamus.')
  $text = $text.Replace('BrainPaths', 'TalamusPaths')
  $text = $text.Replace('BrainConfig', 'TalamusConfig')
  $text = $text.Replace('BrainCliTests', 'TalamusCliTests')
  $text = $text.Replace('BrainModelsTests', 'TalamusModelsTests')
  $text = $text.Replace('BrainGraphTests', 'TalamusGraphTests')
  $text = $text.Replace('BrainSearchTests', 'TalamusSearchTests')
  $text = $text.Replace('BrainPathsConfigTests', 'TalamusPathsConfigTests')
  $text = $text.Replace('brain.json', 'talamus.json')
  $text = $text.Replace('brain project status ok', 'talamus project status ok')
  $text = $text.Replace('brain init', 'talamus init')
  Set-Content -LiteralPath $file.FullName -Value $text -Encoding UTF8
}
```

- [ ] **Step 3: Run renamed tests and verify they fail for the expected reason**

Run:

```powershell
$env:PYTHONPATH="src"
python -m unittest tests.test_talamus_paths_config tests.test_talamus_cli tests.test_talamus_models tests.test_talamus_obsidian_renderer tests.test_talamus_graph tests.test_talamus_search tests.test_talamus_ask -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'talamus'`.

---

### Task 3: Rename Package And Public API

**Files:**
- Rename: `src/brain/` -> `src/talamus/`
- Modify: all Python files under `src/talamus/`

- [ ] **Step 1: Rename package directory**

Run:

```powershell
git mv src/brain src/talamus
```

- [ ] **Step 2: Rewrite package imports and public class names**

Run:

```powershell
$files = Get-ChildItem -LiteralPath src/talamus -Recurse -Include '*.py' -File
foreach ($file in $files) {
  $text = Get-Content -Raw -LiteralPath $file.FullName
  $text = $text.Replace('from brain.', 'from talamus.')
  $text = $text.Replace('import brain', 'import talamus')
  $text = $text.Replace('BrainPaths', 'TalamusPaths')
  $text = $text.Replace('BrainConfig', 'TalamusConfig')
  $text = $text.Replace('brain.json', 'talamus.json')
  $text = $text.Replace('initialized brain project', 'initialized talamus project')
  $text = $text.Replace('brain project status ok', 'talamus project status ok')
  $text = $text.Replace('brain project is not initialized; run `brain init`', 'talamus project is not initialized; run `talamus init`')
  $text = $text.Replace('prog="brain"', 'prog="talamus"')
  $text = $text.Replace('Local-first knowledge compiler core.', 'Talamus local-first knowledge compiler core.')
  Set-Content -LiteralPath $file.FullName -Value $text -Encoding UTF8
}
```

- [ ] **Step 3: Verify key code snippets**

Run:

```powershell
Select-String -Path src/talamus/paths.py -Pattern 'class TalamusPaths', 'talamus.json'
Select-String -Path src/talamus/config.py -Pattern 'class TalamusConfig', 'def default'
Select-String -Path src/talamus/cli.py -Pattern 'prog="talamus"', 'initialized talamus project', 'talamus project status ok'
```

Expected: every pattern is found.

- [ ] **Step 4: Run renamed Talamus tests**

Run:

```powershell
$env:PYTHONPATH="src"
python -m unittest tests.test_talamus_paths_config tests.test_talamus_cli tests.test_talamus_models tests.test_talamus_obsidian_renderer tests.test_talamus_graph tests.test_talamus_search tests.test_talamus_ask -v
```

Expected: PASS.

- [ ] **Step 5: Manual checkpoint**

Do not run `git commit` automatically.

Suggested user-run staging and commit:

```powershell
git add src/talamus tests/test_talamus_*.py
git add -u src/brain tests/test_brain_*.py
git commit -m "refactor: rename brain package to talamus"
```

---

### Task 4: Rename Packaging And Console Script

**Files:**
- Modify: `pyproject.toml`
- Remove: `requirements.txt`

- [ ] **Step 1: Update package metadata**

Edit `pyproject.toml` so the relevant sections are:

```toml
[project]
name = "talamus"
version = "0.1.0"
description = "Local-first knowledge compiler with graph-first retrieval for AI agents."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
authors = [
  { name = "Talamus Contributors" }
]
dependencies = []

[project.optional-dependencies]
docling = ["docling>=2.0"]
dev = []

[project.scripts]
talamus = "talamus.cli:main"
```

Keep the existing build-system and setuptools sections.

- [ ] **Step 2: Remove old requirements file**

Run:

```powershell
git rm requirements.txt
```

Rationale: `requirements.txt` contains legacy prototype dependencies that are not required by the current Talamus foundation. Runtime dependencies now live in `pyproject.toml`.

- [ ] **Step 3: Verify package metadata**

Run:

```powershell
python -c "import tomllib; data=tomllib.load(open('pyproject.toml','rb')); print(data['project']['name']); print(data['project']['scripts']['talamus'])"
```

Expected output:

```text
talamus
talamus.cli:main
```

- [ ] **Step 4: Run Talamus tests**

Run:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -p "test_talamus*.py" -v
```

Expected: PASS.

- [ ] **Step 5: Manual checkpoint**

Do not run `git commit` automatically.

Suggested user-run staging and commit:

```powershell
git add pyproject.toml
git add -u requirements.txt
git commit -m "chore: rename package metadata to talamus"
```

---

### Task 5: Rename Agent Skill And Tool-Calling Docs

**Files:**
- Rename: `skills/brain-knowledge/` -> `skills/talamus-knowledge/`
- Modify: `skills/talamus-knowledge/SKILL.md`
- Modify: `docs/agent-tool-calling.md`

- [ ] **Step 1: Rename skill directory**

Run:

```powershell
git mv skills/brain-knowledge skills/talamus-knowledge
```

- [ ] **Step 2: Rewrite skill content**

Replace `skills/talamus-knowledge/SKILL.md` with:

```markdown
---
name: talamus-knowledge
description: Use when answering questions against a local Talamus knowledge project or when modifying rendered knowledge notes.
---

# Talamus Knowledge Skill

Use this protocol when working with a Talamus project.

## Core Rule

The graph is the primary index. It is not source truth.

Use the graph to decide which notes or normalized source sections to read. Then
answer from the real files with citations.

## Retrieval Order

1. Run `talamus graph query "<question>"`.
2. Read selected final notes through Talamus commands or direct file reads.
3. Follow validated wikilinks when the selected notes point to necessary context.
4. If the graph is insufficient, run `talamus search "<query>"`.
5. If final notes are insufficient, inspect normalized source sections.
6. Cite final notes and their precompiled source references.

## Authoring Rules

- Do not create broken wikilinks.
- Do not cite graph metadata as source truth.
- Do not copy raw source dumps into final notes.
- Preserve raw and normalized provenance.
- Use aliases, tags, and retrieval text to improve future routing.
```

- [ ] **Step 3: Rewrite tool-calling docs**

Replace `docs/agent-tool-calling.md` with:

````markdown
# Talamus Agent Tool Calling Guide

Talamus exposes simple CLI commands that agent frameworks can wrap as tools.

## Graph Routing

```powershell
talamus graph query "<question>"
```

Purpose: identify candidate notes or source sections. The graph is an index, not
the answer source.

## Note Reading

```powershell
talamus notes read <note-id-or-path>
```

Purpose: read real final note content before answering.

## Lexical Fallback

```powershell
talamus search "<query>"
```

Purpose: recover candidates when graph routing is insufficient.

## Source Reading

```powershell
talamus sources read <source-section-id-or-path>
```

Purpose: inspect normalized sources when final notes do not contain enough
information.

## Validation

```powershell
talamus validate
```

Purpose: check links, provenance, graph/index freshness, and project structure.

## Review Queue

```powershell
talamus review list
```

Purpose: inspect low-confidence conversion, missing concepts, and items needing
human judgment.
````

- [ ] **Step 4: Verify docs mention Talamus commands**

Run:

```powershell
rg -n "talamus graph query|talamus search|graph is the primary index|not source truth" skills/talamus-knowledge/SKILL.md docs/agent-tool-calling.md
```

Expected: all phrases are found.

- [ ] **Step 5: Manual checkpoint**

Do not run `git commit` automatically.

Suggested user-run staging and commit:

```powershell
git add skills/talamus-knowledge docs/agent-tool-calling.md
git add -u skills/brain-knowledge
git commit -m "docs: rename agent guidance to talamus"
```

---

### Task 6: Rewrite Workspace Instructions And README

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Create: `README.md`

- [ ] **Step 1: Replace AGENTS.md**

Replace `AGENTS.md` with:

````markdown
# Codex Workspace Instructions

This repository is Talamus: an open-source, local-first knowledge compiler with
graph-first retrieval.

Before modifying product architecture, retrieval behavior, generated knowledge
storage, or agent-facing protocol, read:

```text
docs/superpowers/specs/2026-05-27-local-first-knowledge-pipeline-v1-design.md
docs/superpowers/specs/2026-05-28-talamus-repository-cleanup-design.md
```

Current implementation focus:

```text
docs/superpowers/plans/2026-05-28-talamus-repository-cleanup.md
```

Rules:

- Product code lives under `src/talamus/`.
- Tests for active product code are named `tests/test_talamus_*.py`.
- The CLI command is `talamus`.
- The default config file is `talamus.json`.
- The graph is an index and routing layer, not source truth.
- Answers must be grounded in real Markdown notes or normalized source files.
- Do not commit `.claude/` or generated caches.
````

- [ ] **Step 2: Replace CLAUDE.md**

Replace `CLAUDE.md` with:

````markdown
# Claude Code Workspace Instructions

This repository is Talamus: an open-source, local-first knowledge compiler with
graph-first retrieval.

Use the same development protocol as Codex:

```text
AGENTS.md
```

Operational expectations:

- Work against `src/talamus/` and `tests/test_talamus_*.py`.
- Use `talamus` as the CLI name.
- Treat the graph as an index, not source truth.
- Do not reintroduce legacy personal-workspace folders.
- Do not commit `.claude/` or generated caches.
````

- [ ] **Step 3: Create README.md**

Create `README.md`:

````markdown
# Talamus

Talamus is a local-first knowledge compiler with graph-first retrieval for AI
agents and humans.

It turns source material into source-grounded notes, builds a lightweight graph
as the routing index, and helps agents read the real Markdown files before
answering with citations.

## Status

Talamus is in early foundation development. The current code includes:

- project initialization
- canonical note/source models
- Obsidian Markdown rendering
- deterministic graph generation
- built-in BM25 fallback search
- graph-first context retrieval

Conversion, OCR, LLM note extraction, scheduling, and UI are planned after the
core foundation is stable.

## Development

Run tests:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

Smoke test the CLI:

```powershell
$tmp = Join-Path $env:TEMP "talamus-smoke"
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
$env:PYTHONPATH="src"
python -m talamus.cli init --root $tmp
python -m talamus.cli status --root $tmp
python -m talamus.cli doctor --root $tmp
```

## Retrieval Principle

The graph is an index, not source truth. Talamus uses the graph to route a
question to candidate notes or sources, then reads the real Markdown files before
answering.

## License

Apache-2.0.
````

- [ ] **Step 4: Verify active docs do not use old product terms**

Run:

```powershell
rg -n "FDE Brain|AI Space|Dual Graph|Graphify|graphify|brain init|brain\\.json|python -m brain|from brain" AGENTS.md CLAUDE.md README.md docs/agent-tool-calling.md skills/talamus-knowledge src tests pyproject.toml
```

Expected: no output.

- [ ] **Step 5: Manual checkpoint**

Do not run `git commit` automatically.

Suggested user-run staging and commit:

```powershell
git add AGENTS.md CLAUDE.md README.md
git commit -m "docs: describe talamus repository"
```

---

### Task 7: Remove Legacy Prototype Folders And Tests

**Files:**
- Remove: `AI Space/`
- Remove: `FDE Brain/`
- Remove: `tools/fde_brain/`
- Remove: legacy tests listed in the file structure section
- Remove: `tests/fixtures/generate_test_book.py`

- [ ] **Step 1: Verify deletion targets are inside workspace**

Run:

```powershell
$workspace = (Resolve-Path '.').Path
$targets = @('AI Space', 'FDE Brain', 'tools/fde_brain')
foreach ($target in $targets) {
  $resolved = (Resolve-Path -LiteralPath $target).Path
  if (-not $resolved.StartsWith($workspace)) {
    throw "Refusing to delete outside workspace: $resolved"
  }
  Write-Output "$target -> $resolved"
}
```

Expected: all three paths resolve under the current repository root.

- [ ] **Step 2: Remove tracked legacy folders**

Run:

```powershell
git rm -r -- 'AI Space' 'FDE Brain' 'tools/fde_brain'
```

Expected: Git stages deletions for tracked files under those directories.

- [ ] **Step 3: Remove legacy tests and fixture**

Run:

```powershell
git rm -- `
  tests/test_ask.py `
  tests/test_chapters.py `
  tests/test_classify.py `
  tests/test_distill.py `
  tests/test_distill_local.py `
  tests/test_distill_v3.py `
  tests/test_graphify.py `
  tests/test_ingest.py `
  tests/test_layout.py `
  tests/test_length.py `
  tests/test_normalize.py `
  tests/test_normalize_v2.py `
  tests/test_ocr.py `
  tests/test_paths.py `
  tests/test_pdf_render.py `
  tests/test_preflight.py `
  tests/test_registry.py `
  tests/test_rerun_local_distill.py `
  tests/test_run_log.py `
  tests/test_validate_obsidian.py `
  tests/test_validate_workspace.py `
  tests/fixtures/generate_test_book.py
```

Expected: Git stages those test deletions. If any path is already deleted, run `git ls-files tests` and delete only the remaining legacy paths.

- [ ] **Step 4: Remove generated Python caches locally**

Run this safety-checked cleanup:

```powershell
$workspace = (Resolve-Path '.').Path
$caches = Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__'
foreach ($cache in $caches) {
  $resolved = $cache.FullName
  if (-not $resolved.StartsWith($workspace)) {
    throw "Refusing to delete outside workspace: $resolved"
  }
  Remove-Item -LiteralPath $resolved -Recurse -Force
}
```

Expected: local `__pycache__/` directories are removed and not staged as tracked files.

- [ ] **Step 5: Verify only Talamus tests remain**

Run:

```powershell
Get-ChildItem -LiteralPath tests -File | Select-Object -ExpandProperty Name
```

Expected output contains only:

```text
test_talamus_ask.py
test_talamus_cli.py
test_talamus_graph.py
test_talamus_models.py
test_talamus_obsidian_renderer.py
test_talamus_paths_config.py
test_talamus_search.py
```

- [ ] **Step 6: Manual checkpoint**

Do not run `git commit` automatically.

Suggested user-run staging and commit:

```powershell
git add -u 'AI Space' 'FDE Brain' tools/fde_brain tests
git commit -m "chore: remove legacy prototype workspace"
```

---

### Task 8: Final Talamus Verification And Hygiene

**Files:**
- Modify: none unless verification exposes a defect

- [ ] **Step 1: Run full remaining test suite**

Run:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

Expected: PASS with only Talamus tests.

- [ ] **Step 2: Run Talamus CLI smoke test**

Run:

```powershell
$tmp = Join-Path $env:TEMP "talamus-cleanup-smoke"
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
$env:PYTHONPATH="src"
python -m talamus.cli init --root $tmp
python -m talamus.cli status --root $tmp
python -m talamus.cli doctor --root $tmp
Test-Path (Join-Path $tmp "talamus.json")
Test-Path (Join-Path $tmp "knowledge/notes")
```

Expected:

```text
initialized talamus project at ...
talamus project status ok
storage: obsidian
...
True
True
```

- [ ] **Step 3: Verify no legacy tracked paths remain**

Run:

```powershell
git ls-files | rg "^(AI Space|FDE Brain|tools/fde_brain|src/brain|skills/brain-knowledge)"
if ($LASTEXITCODE -eq 0) { throw "legacy tracked paths remain" } else { "no legacy tracked paths" }
```

Expected:

```text
no legacy tracked paths
```

- [ ] **Step 4: Verify active product files do not use old names**

Run:

```powershell
rg -n "FDE Brain|AI Space|Dual Graph|Graphify|graphify|tools\\.fde_brain|from brain|python -m brain|brain init|brain\\.json" AGENTS.md CLAUDE.md README.md docs/agent-tool-calling.md skills/talamus-knowledge src tests pyproject.toml
if ($LASTEXITCODE -eq 0) { throw "old active product references remain" } else { "active product references are clean" }
```

Expected:

```text
active product references are clean
```

- [ ] **Step 5: Inspect final git status**

Run:

```powershell
git status --short --untracked-files=all
```

Expected:

- staged or unstaged changes are limited to Talamus rename, docs rewrite, legacy deletions, and this cleanup plan/spec if the user wants to include them.
- no `.claude/` files are staged.
- no untracked `AI Space/graph/brain/graphify-out/` files are staged.
- no `__pycache__/` files are present.

- [ ] **Step 6: Manual final commit**

Do not run `git commit` automatically.

Suggested user-run final commit after review:

```powershell
git add AGENTS.md CLAUDE.md README.md docs/agent-tool-calling.md pyproject.toml src/talamus tests/test_talamus_*.py skills/talamus-knowledge
git add -u
git commit -m "refactor: reset repository as talamus"
```

Before running that commit, the user should inspect staged files:

```powershell
git diff --cached --name-status
```

---

### Task 9: Post-Commit Physical Folder Rename Instructions

**Files:**
- Modify: none

- [ ] **Step 1: Close tools using the old workspace**

Close or stop:

```text
Codex sessions using the old path
Claude Code sessions using the old path
Obsidian vault opened at the old path
terminals with current directory inside the old path
```

- [ ] **Step 2: Rename the folder outside the active session**

From a new PowerShell window whose current directory is not inside the old repo:

```powershell
Rename-Item `
  -LiteralPath 'C:\Users\Giovanni Crapuzzi\Documents\Formazione\FDE Brain' `
  -NewName 'Talamus'
```

Expected new path:

```text
C:\Users\Giovanni Crapuzzi\Documents\Formazione\Talamus
```

- [ ] **Step 3: Reopen tools at the new path**

Open the repository from:

```text
C:\Users\Giovanni Crapuzzi\Documents\Formazione\Talamus
```

Run:

```powershell
git status --short
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

Expected: same repo state as before folder rename, tests pass.

---

## Self-Review Checklist

Spec coverage:

- Talamus naming: Tasks 2, 3, 4, 5, 6.
- CLI `talamus`: Tasks 3, 4, 8.
- Config `talamus.json`: Tasks 2, 3, 8.
- Remove legacy tracked folders: Task 7.
- Remove legacy tests and fixture: Task 7.
- Rewrite active docs: Tasks 5 and 6.
- Avoid physical workspace rename in-session: Task 9.
- User-controlled commits: every checkpoint says not to run `git commit` automatically.

Placeholder scan:

- No unresolved marker tokens are used.
- Each code-changing task has exact commands or complete replacement content.
- Each verification task has exact commands and expected results.

Type consistency:

- `TalamusPaths` replaces `BrainPaths` everywhere.
- `TalamusConfig` replaces `BrainConfig` everywhere.
- `talamus.json` replaces `brain.json` in code and tests.
- `talamus.cli:main` is the only console entrypoint.
