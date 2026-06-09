# Configuration

## `talamus.json`

Created by `talamus init` in the brain directory. Fields:

| Field | Meaning | Default |
| --- | --- | --- |
| `llm_provider` | Which LLM engine to use | `claude-cli` (auto-detected) |
| `llm_model` | Model name for the engine (optional) | engine default |
| `storage_provider` | Notes rendering | `obsidian` |
| `graph_provider` | Graph index | `deterministic-json` |
| `search_provider` | Lexical search | `builtin-bm25` |
| `pdf_converter` / `ocr_provider` / `ocr_model` | Sources (roadmap) | docling / ollama / glm-ocr |

### Engines (`llm_provider`)

- `claude-cli` — your Claude subscription (default if `claude` is on PATH).
- `ollama` — a local model, fully offline. Set `llm_model` (e.g. `llama3`).
- `anthropic-api` (or `api`) — the Anthropic API. Needs `ANTHROPIC_API_KEY`.

*(Gemini, Codex and OpenAI providers are on the roadmap — same adapter pattern.)*

## Environment variables

| Variable | Effect |
| --- | --- |
| `TALAMUS_<FIELD>` | Override any config field, e.g. `TALAMUS_LLM_PROVIDER=ollama`, `TALAMUS_LLM_MODEL=llama3`. |
| `TALAMUS_HOME` | Where global brains live (default `~/talamus`). |
| `ANTHROPIC_API_KEY` | API key for the `anthropic-api` engine. |
| `TALAMUS_LOG` | Set (any value) to enable DEBUG logging — same as `--verbose`. |

## Which brain is used

When you don't pass an explicit `--root`, Talamus resolves the brain in this order:

1. `--root <dir>` — an explicit directory.
2. `--brain <name>` — a named global brain under `TALAMUS_HOME`.
3. `--global` — the default global brain (`TALAMUS_HOME/default`).
4. **Project brain** — the nearest ancestor of the current directory that contains
   a `talamus.json`.
5. **Global default** — `TALAMUS_HOME/default`.

`talamus where` prints the resolved brain; `talamus brains` lists the global ones.
