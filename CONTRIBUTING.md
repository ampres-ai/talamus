# Contributing to Talamus

Thanks for your interest! Talamus is local-first and stdlib-only at the core, with
optional adapters behind extras. Participation is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md).

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

Keep changes focused, explain the *why*, and make sure the gate is green.

## Releases

PyPI publishing uses Trusted Publishing, not repository secrets. To publish a
release:

1. Update `version` in `pyproject.toml`.
2. Run `python dev.py`.
3. Commit, push, and merge the version change into `main`.
4. Create a **draft** GitHub release tagged `vX.Y.Z` at the merged release
   commit, matching the exact `pyproject.toml` version.
5. Dispatch `Publish release` with that tag. Wait for its read-only quality
   gate and draft-asset job to attach the wheel, source archive, checksums, and
   commit-bound release manifest.
6. Publish the draft. The `published` event uploads those exact checked files
   to PyPI and then publishes `server.json` to the official MCP Registry.

The same workflow input safely recovers a published release: it compares
existing PyPI hashes and MCP metadata before deciding whether either immutable
version still needs publication. Configure the PyPI Trusted Publisher for
project `talamus` with owner `ampres-ai`, repository `talamus`, workflow
`publish.yml`, and environment `pypi`.

## Release checklist

Before tagging a release, verify:

- `python dev.py` green on the release commit; CI green on all three OSes
  (including the extras job).
- `python -m mkdocs build --strict` clean.
- `python -m build` and `python -m twine check dist/*` succeed.
- Fresh-venv install of the newly built wheel works, then `talamus --version`,
  `talamus demo`, and `talamus search "embedding"` succeed.
- Benchmark artifacts under `benchmarks/results/` are current for any number
  the README claims.
- README and docs match `talamus --help`; CHANGELOG updated; cache migrations
  documented (migrate with `talamus reindex`).
- No caches or brains committed; secret-redaction tests green; Gitleaks scans
  the complete Git history with no unreviewed findings.
- Manual smoke: `talamus ui` renders all ten views; MCP handshake works with
  a real client (`talamus mcp serve --root .`).

## Where the project truth lives

- [docs/design-principles.md](docs/design-principles.md) — the binding design
  choices and why they exist. Changes that break one need a very good,
  measured reason.
- [docs/architecture.md](docs/architecture.md) — how every part works, module
  by module. Update it in the same change that alters public behavior.
- [docs/benchmarks.md](docs/benchmarks.md) — the measured numbers; every
  public claim traces to a committed artifact in `benchmarks/results/`.
- [ROADMAP.md](ROADMAP.md) — where the project is going.
