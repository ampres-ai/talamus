# Contributing to Talamus

Thanks for your interest! Talamus is local-first and stdlib-only at the core, with
optional adapters behind extras.

## Setup

```bash
pip install -e ".[dev,mcp]"
```

## The quality gate

One command runs everything (lint, format, types, tests):

```bash
python dev.py            # check
python dev.py --fix      # autofix lint + format, then check
```

This must be green before a change is merged. CI runs the same gate on
Windows / macOS / Linux across Python 3.11–3.13.

- **Lint & format**: `ruff` (line length 100).
- **Types**: `mypy` (the core is fully typed).
- **Tests**: `python -m unittest discover -s tests`. Add a focused test with each change.

## Conventions

- Core (`src/talamus/`) stays **Python stdlib-only**; new dependencies go behind an
  optional extra and an adapter.
- The graph is an **index, not the truth**; notes (Markdown + cache JSON) are the truth.
- Keep modules small and single-purpose; follow the existing patterns.

## Docs

```bash
pip install -e ".[docs]"
mkdocs serve            # preview the docs site at http://127.0.0.1:8000
```

## Pull requests

Keep changes focused, explain the *why*, and make sure the gate is green. See the
[architecture doc](docs/architecture.md) for module responsibilities and the
[roadmap](docs/superpowers/specs/2026-06-08-talamus-roadmap.md) for direction.
