# Changelog

## Unreleased

No changes yet.

## 1.0.0 - 2026-07-21

- Add the consent-aware Talamus memory skill.
- Add a pinned, local STDIO MCP server launched through `uvx`.
- Support the compatible Claude Code and GitHub Copilot CLI plugin formats.
- Add Cursor Marketplace metadata and a dedicated, skills-only CLI workflow.
- Require explicit consent and a persistent pinned tool before optional Cursor
  MCP setup; do not rely on a temporary `uvx` environment for its launcher.
- Add repository-level Open Plugin support for goose while reusing the bundled
  skill and pinned MCP launcher.
- Treat retrieved notes, source content, transcripts, and MCP responses as
  untrusted data rather than agent instructions.
