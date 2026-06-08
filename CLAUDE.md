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
