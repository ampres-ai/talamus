# Changelog

All notable changes to Talamus are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning once it reaches a public release.

## [Unreleased]

Pre-release. The project was renamed **Kortex → Talamus**.

### Added

- **CLI**: no-arg status panel, `quickstart`, smart `init` (engine auto-detect,
  `--engine`), enhanced `doctor` (engine/cache/notes), `--json` on read commands,
  global+project brain **scoping** (`--root` / `--brain` / `--global`, `TALAMUS_HOME`),
  `brains`, `where`, `export`/`import`, shell `completion`, and `demo`
  (an instant, LLM-free example brain).
- **Engines**: pluggable LLM adapters via a `build_provider` factory — `claude-cli`,
  local **Ollama**, and the **Anthropic API**; selected from config (`llm_provider`,
  `llm_model`). The CLI and MCP server build the engine from config.
- **Onboarding**: `talamus mcp install` (writes `.mcp.json`) and `talamus hook` /
  `hook-run` (a robust Claude Code capture hook). 10-minute quickstart.
- **Quality**: `ruff` + `mypy` + a `dev.py` runner, multi-OS CI, an exception
  hierarchy with actionable messages, logging, config validation, **normalized
  source files written to disk**, cache schema versioning, and a benchmark harness.
- **Docs**: a 10k-star README, internal architecture doc, a security policy, and
  this docs site.

### Changed

- Package `kortex` → `talamus`; CLI `kortex` → `talamus`; config `kortex.json` →
  `talamus.json`; cache `.kortex/` → `.talamus/`; env `KORTEX_*` → `TALAMUS_*`.
