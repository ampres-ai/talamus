# Release checklist

Run before tagging a release. Nothing ships with a red gate.

## Quality

- [ ] `python dev.py` green (ruff + mypy + unittest) on the release commit
- [ ] CI green on Windows / macOS / Linux (including the `extras` job: ui+pdf)
- [ ] `python -m mkdocs build --strict` clean
- [ ] Fresh venv install: `pip install -e ".[dev,mcp]"` then `talamus --version`,
      `talamus demo`, `talamus search "embedding"`

## Measurement (PRD §17.2)

- [ ] `talamus eval --cases examples/eval-cases-real.json` run and recorded
- [ ] `talamus eval --scale` meets latency targets (10k p95 < 100 ms; 100k usable)
- [ ] Benchmark artifacts updated under `benchmarks/results/` (dated JSON)

## Claims & docs

- [ ] README claims match reality, each labelled shipped / experimental / roadmap
- [ ] CHANGELOG updated; commands in docs match `talamus --help`
- [ ] Cache migrations documented (current: v2 — migrate with `talamus reindex`)

## Safety (PRD §17.4)

- [ ] No `.claude/`, caches or brains committed (`git status` clean of them)
- [ ] Scan defaults still exclude secret-like files; redaction tests green
- [ ] Destructive commands still require confirmation or explicit flags

## Runtime (manual, needs a display)

- [ ] `talamus ui` opens the web workbench; Home / Ask / Graph / Library / Import / Review / Ontology / Brains / System render
- [ ] the workbench serves in a plain browser too; narrow width readable
- [ ] MCP handshake with a real client (`talamus mcp install` + `/mcp`)
