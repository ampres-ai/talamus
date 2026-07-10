# Configuration

## `talamus.json`

Created by `talamus init` in the brain directory. Fields:

| Field | Meaning | Default |
| --- | --- | --- |
| `llm_provider` | Which LLM engine to use | `claude-cli` (auto-detected) |
| `llm_model` | Model name for the engine (optional) | engine default |
| `language` | The language notes are written in (prose). Prompts are always English (cheap local models follow English best); the machine layer (relation verbs, canonical aliases, half of `retrieval_text`) stays English-canonical for cross-language search. | auto from system locale |
| `storage_provider` | Notes rendering | `obsidian` |
| `graph_provider` | Graph index | `deterministic-json` |
| `search_provider` | Lexical search | `builtin-bm25` |
| `pdf_converter` / `ocr_provider` / `ocr_model` | Source conversion. Today only `pypdf` (PDFs) is wired; OCR is not. A richer converter (docling) and OCR are on the [roadmap](https://github.com/GCrapuzzi/Talamus-Wiki/blob/main/ROADMAP.md). | `pypdf` / `none` / `none` |

### Engines (`llm_provider`)

- `claude-cli` — your Claude subscription (default if `claude` is on PATH).
- `codex-cli` (or `codex`) — your ChatGPT subscription (Codex is bundled with it).
- `gemini-cli` (or `gemini`) — your Gemini subscription.
- `opencode` — opencode, with whatever providers you configured in it.
- `antigravity-cli` (or `agy`) — Google Antigravity.
- `ollama` — a local model, fully offline. Set `llm_model` (e.g. `llama3`).
- `anthropic-api` (or `api`) — the Anthropic API. Needs `ANTHROPIC_API_KEY`.

Every engine goes through per-task **model+effort tiering** (`task_tiers` and
`provider_models` in `talamus.json` override the cost-minimizing defaults);
`TALAMUS_ENGINE_TIMEOUT` caps a single engine call in seconds (default 600).

## Environment variables

| Variable | Effect |
| --- | --- |
| `TALAMUS_<FIELD>` | Override any config field, e.g. `TALAMUS_LLM_PROVIDER=ollama`, `TALAMUS_LLM_MODEL=llama3`. |
| `TALAMUS_HOME` | Where global brains live (default `~/talamus`). |
| `TALAMUS_CONTEXT_BUDGET` | Max tokens of note context sent to the engine per answer (default `6000`); keeps answer cost flat as the brain grows. |
| `ANTHROPIC_API_KEY` | API key for the `anthropic-api` engine. |
| `OLLAMA_HOST` | Ollama HTTP endpoint for local model calls when HTTP options are used (default `http://localhost:11434`). |
| `TALAMUS_UI_TOKEN` | Advanced: override the random per-launch workbench token. Normally leave unset. |
| `TALAMUS_MONO_TRIGRAM_SCALE` | Advanced retrieval tuning: trigram scale for monolingual-ASCII corpora (default `0.3`). |
| `TALAMUS_LOG` | Set (any value) to enable DEBUG logging — same as `--verbose`. |

## Related command flags

- Global output: `--plain` / `--no-color` disables ANSI color; `--json` is for machine-readable read output.
- Setup/init: `talamus init --profile docs|code|all --scan` initializes a brain and shows a scan plan.
- Consent gates: `talamus ingest --yes` confirms large multi-chunk ingest; `talamus enrich --yes` confirms enrichment batches.
- Scan limits: `talamus scan --max-files N --include GLOB --exclude GLOB` shapes the repo plan before any LLM spend.
- UI: `talamus ui --web --port N` opens the React workbench in a browser on a chosen port.
- Ontology: `reject` / `deprecate` accept `--reason`; `eval` accepts `-k`; `stability` accepts `--runs`.

## Which brain is used

When you don't pass an explicit `--root`, Talamus resolves the brain in this order:

1. `--root <dir>` — an explicit directory.
2. `--brain <name>` — a named global brain under `TALAMUS_HOME`.
3. `--global` — the default global brain (`TALAMUS_HOME/default`).
4. **Project brain** — the nearest ancestor of the current directory that contains
   a `talamus.json`.
5. **Global default** — `TALAMUS_HOME/default`.

`talamus where` prints the resolved brain; `talamus brains` lists the global ones.
