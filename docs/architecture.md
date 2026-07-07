# Talamus — Internal Architecture

A short map of the modules and data flow. The full developer deep-dive lives in
[`dev/ARCHITECTURE.md`](https://github.com/GCrapuzzi/Talamus-Wiki/blob/main/dev/ARCHITECTURE.md).
Core is **Python stdlib-only**; optional features (UI, MCP, PDF, benchmarks)
live behind extras and adapters.

## Storage model (hybrid)

- `notes/*.md` — the **human-editable view** (Obsidian-compatible), each carries a stable `id` in frontmatter.
- `.talamus/cache/notes/<id>.json` — the **machine truth** (provenance, relations, confidence).
- `.talamus/{raw,normalized}/` — the preserved **sources** (raw copy + normalized view).
- `.talamus/cache/{index.sqlite,postings.json,graph.json,ontology.json,overview.json,schema.json}` — **derived indexes**, always rebuildable.
- `talamus reindex` re-reads the Markdown for human fields and merges, preserving machine fields.

## Modules (`src/talamus/`)

| Module | Responsibility |
|---|---|
| `paths.py` | `TalamusPaths`: every filesystem location. |
| `config.py` | `TalamusConfig`: provider selection; load/save/validate/env-override. |
| `errors.py` | Exception hierarchy (`TalamusError` + actionable subclasses). |
| `log.py` | Quiet-by-default logging (`--verbose` / `TALAMUS_LOG`). |
| `adapters/llm.py` | Seven engines: `claude-cli`, `codex-cli`, `gemini-cli`, `opencode`, `antigravity-cli`, `ollama`, `anthropic-api`. |
| `normalize.py` | Raw text -> `NormalizedPackage` (sections). |
| `session.py` | Agent transcript+diff -> `NormalizedPackage` (capture); compaction + worth-remembering gate. |
| `extract.py` | `NormalizedPackage` + LLM -> `CanonicalNote[]` (the librarian prompt). |
| `models.py` | `CanonicalNote`, `SourceRef` (provenance), `Relation`, `ProposedLink`. |
| `linking.py` | `NoteRegistry` — resolve wikilinks within a batch. |
| `naming.py` | `note_slug` / `note_filename` — cross-OS-safe names. |
| `storage/obsidian.py` | Render a note to Markdown with `[[wikilinks]]`. |
| `noteparse.py` | Parse Markdown back to human fields (for `reindex`). |
| `store.py` | Cache write + `merge_notes`, `load_notes`, `rebuild_indexes`, `reindex`, cache versioning. |
| `graph.py` / `ontology.py` | Derived graph and typed ontology indexes. |
| `indexes.py` / `search.py` | Persistent lexical + trigram search (`sqlite` FTS5 preferred, postings fallback). |
| `ask.py` | Overview/domain routing + LLM query expansion + ranked persistent-index selection + fallback + cited answer. |
| `recall.py` | Read SDK: `search_notes`, `read_note_text`, `recall_context`, `concept_neighbors`. |
| `ingest.py` | Write SDK: `_compile_package` (shared), `ingest_file`, `remember_session`, `ingest_text`. |
| `cli/` | The `talamus` CLI package: parser, dispatch, and command groups. |
| `mcp_server.py` | Optional MCP server: read tools plus controlled write/review tools. |
| `webapi/` + `webui/` | FastAPI + React workbench launched by `talamus ui`. |

## Data flow

**Write (ingest):**

```text
source -> normalize_text / normalize_session -> NormalizedPackage
       -> write .talamus/normalized/<name>.md
       -> extract_notes (LLM) -> CanonicalNote[]
       -> write_note_json (cache truth, merge same-id)
       -> render_note_markdown (notes/*.md, wikilinks resolved batch-wide)
       -> rebuild_indexes (search + graph + ontology + overview/cache metadata)
```

**Read (recall / ask):**

```text
question -> route over overview tree/domains
         -> LLM query expansion
         -> rank selected domain members with the persistent index
         -> add global escape seeds + fallback when needed
         -> fit notes to the context budget
         -> answer_question (LLM composes a cited answer)
```

Without an overview, the read path starts from persistent-index seeds, expands
typed ontology neighbors when useful, and retries with query expansion if the
first pass finds nothing.

Surfaces are intended to stay thin over shared `services/` contracts. CLI and
MCP use those services for the current public surfaces; a few registry commands
still have direct wiring. The React workbench is the current UI, opened by
`talamus ui` in a pywebview window by default or a browser with `--web`.

## Principles

Local-first · the LLM reasons and chooses · indexes are **derived**, not the
truth · stdlib core + optional adapters · every answer reads real notes and
cites sources.
