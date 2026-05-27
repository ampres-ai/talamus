# FDE Brain Runbook

## Validate Workspace

```powershell
python -m tools.fde_brain.validate_workspace --root .
```

Expected:

```text
workspace validation ok
```

## Check Local Engines

```powershell
python -m tools.fde_brain.preflight
```

Required tools:

- Claude Code
- Codex CLI
- Git
- Ollama
- GLM-OCR model in Ollama
- Gemma distillation model in Ollama
- Graphify

## Ingest Pending Files

```powershell
python -m tools.fde_brain.ingest --root .
```

Optional flags:

- `--no-commit` runs the pipeline without creating the final git commit.
- `--dry-run` validates and enumerates pending files without moving, logging, or committing.
- `--distill-model gemma4:e4b` selects the local Ollama model used for section-level distillation.

Flow:

1. Read files from `AI Space/pending/`.
2. Archive originals into `AI Space/raw/<category>/`.
3. Normalize each source into a V2 package:
   - `AI Space/normalized/<category>/<source_slug>/manifest.json`
   - `AI Space/normalized/<category>/<source_slug>/sections/*.md`
   - `AI Space/normalized/<category>/<source_slug>/quality-report.json`
4. Distill normalized sections locally with Gemma through Ollama.
5. Write Obsidian-native final notes to `FDE Brain/` only when stable reusable knowledge is found.
6. Update `AI Space/normalized/registry.json`.
7. Mark Source Graph stale after normalized changes and Brain Graph stale after promoted notes.
8. Write the run log before the optional ingestion commit.

The pipeline does not call Claude automatically. Claude is manual fallback only.

## Refresh Graphs

Print the Brain Graph command:

```powershell
python -m tools.fde_brain.graphify brain --root .
```

Run the Brain Graph refresh:

```powershell
python -m tools.fde_brain.graphify brain --root . --run
```

Print the Source Graph command:

```powershell
python -m tools.fde_brain.graphify sources --root .
```

Run the Source Graph refresh:

```powershell
python -m tools.fde_brain.graphify sources --root . --run
```

Default Graphify extraction:

```powershell
graphify extract <path> --backend ollama --model gemma4:e4b --max-concurrency 1 --token-budget 12000 --api-timeout 1800 --out <graph-dir>
```

Graphify writes graph files under:

```text
<graph-dir>/graphify-out/graph.json
```

If refresh fails, `.stale` remains in the graph directory.

## Ask The Knowledge Base

Print citation-ready context for any agent:

```powershell
python -m tools.fde_brain.ask context "your question" --root .
```

Draft a cited local answer with Gemma:

```powershell
python -m tools.fde_brain.ask answer "your question" --model gemma --root . --read-only
```

Other answer backends:

```powershell
python -m tools.fde_brain.ask answer "your question" --model claude --root .
python -m tools.fde_brain.ask answer "your question" --model codex --root .
```

`ask` uses Graphify for routing when graph files exist, then reads real Markdown files before producing context or answers.

## Pending Folder Contract

`AI Space/pending/` is a temporary drop zone. It may contain arbitrary files and notes. It should be empty after a successful scheduled ingestion run, but only after files are safely archived, reviewed, or failed.
