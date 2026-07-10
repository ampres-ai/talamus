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
- `antigravity-cli` (or `agy`) — Google Antigravity, your Gemini subscription.
- `opencode` — opencode, with whatever providers you configured in it.
- `ollama` — a local model, fully offline. Set `llm_model` (e.g. `llama3`).
- `anthropic-api` (or `api`) — the Anthropic API. Needs `ANTHROPIC_API_KEY`.
- `gemini-cli` (or `gemini`) — **deprecated**: Google replaced the standalone
  gemini CLI with Antigravity. The adapter still works if you have the old
  binary, but Talamus warns and you should switch to `antigravity-cli`.

Every engine goes through per-task **model+effort tiering** (`task_tiers` and
`provider_models` in `talamus.json` override the cost-minimizing defaults);
`TALAMUS_ENGINE_TIMEOUT` caps a single engine call in seconds (default 600).

## Language support (honest status)

Talamus is built to be language-agnostic, and the parts that involve the LLM
already are. The built-in search index has known limits. What works today:

- **Note prose: any language.** Set `language` (or let the locale decide) and
  the LLM writes notes in your language — German, Chinese, anything it speaks.
- **Cross-language retrieval: any language, via the machine layer.** Every
  note also carries an English canonical alias and bilingual retrieval text
  written by the LLM at ingest, and `ask` / `search --smart` translate your
  question into the corpus vocabulary. This bridge is the LLM's work, so it
  is not tied to any hardcoded language list.
- **Plain `search`: best for Latin-script languages.** The lexical index
  stems Italian and English suffixes, and the character-trigram channel
  covers Latin scripts (accents included) — German, French, Spanish work
  well. Non-Latin scripts (Chinese, Japanese, Russian, Arabic...) currently
  produce no index tokens: on those corpora use `ask` or `search --smart`,
  which work through the LLM bridge. Unicode-aware tokenization is on the
  [roadmap](https://github.com/GCrapuzzi/Talamus-Wiki/blob/main/ROADMAP.md).

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
