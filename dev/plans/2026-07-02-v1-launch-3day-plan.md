# V1 in 3 days — scope decisions + execution plan

**Decision date:** 2026-07-02 · **Target:** v1.0 ready to publish by 2026-07-05.
**Authority:** ROADMAP §0.7 launch bar + PRODUCT.md numeric bars. When this plan and
the roadmap disagree, this plan is the 3-day cut; the roadmap keeps the full vision.

## Where we stand (verified today)

- P0 clean-code: **done, merged** (no Italian chrome in `src/`; `cli/` split).
- P1 service spine: **done** (CLI/MCP/webapi/UI on `services/`).
- P1.5 corpora: round 1 **done** (garden corpus, FAST/HEAVY tiers).
- P2 engines: **tiering DONE + merged** (per-task model/effort, all call sites).
  Remaining: timeout + usage-limit handling; kimi/opencode.
- P7 UI: **workbench built** (9 React views, brain switch, d3 graph, Aurora).
- MCP: 8 read + 6 write tools on services, one-command install.
- Quality bars (PRODUCT.md): ask 0.972 ✓, smart search 0.972 ✓, latency ✓,
  routing ✓, multi-OS CI ✓, floors ✓. Pending: 100k bench, negatives set,
  (ollama e2e actually proven by RS8 — table row stale).

## The cut (decisions)

| # | Decision | Rationale |
|---|---|---|
| D1 | **IN: P2 slice 2 — hard per-call timeout + usage-limit detection** (clear resumable message; NO auto-fallback engine switching) | RS8 measured 12.5% local generations >90 s; gemini-on-Windows hang; worst possible first-run experience if missing |
| D2 | **CUT: kimi-cli / opencode adapters** → post-launch | claude+codex+gemini+ollama already cover archetypes A and B; adapters are the ideal first-contributor area |
| D3 | **IN: minimal migration import — Obsidian/markdown vault** (`talamus import-vault`): 1:1 notes, titles + wikilinks preserved, NO LLM (fast, free, light); llm_wiki only if its on-disk format is available; **CUT Notion** (its export is md anyway) | The launch bar demands the switching wall removed; the md importer covers Obsidian AND Notion-export with one code path |
| D4 | **CUT: P3 entirely** (chunking overlap, docling/OCR, raw-prune) → post-launch | Quality R&D, not launch-blocking; ingest works and is resumable |
| D5 | **CUT: P5 cost display in UI, P8 CLI aesthetics** → post-launch | Evidence already exists in research docs; chrome is English and decent |
| D6 | **CUT: P6 "magic loop" measurement** → post-launch | The loop works (hook → remember_session); measuring its magic is R&D |
| D7 | **CUT: PyInstaller desktop binary** → post-launch; v1 ships `pip install talamus` + `talamus ui` (pywebview) + `[ui]` extra | Packaging risk in a 3-day window; pip is the OSS-native channel |
| D8 | **IN: P10/P11 core** — setup e2e verify, clean-venv install, 100k bench, negatives 6→30, README/docs pass, demo script, messaging, version 1.0.0 + tag + `twine check` | This IS the launch |
| D9 | **Background workers:** codex CLI (`gpt-5.5` medium for code, `gpt-5.4-mini` for mechanical, `xhigh` reserved) and/or `agy -p` for secondary tasks: 100k bench run, negatives expansion, docs sweep | Maintainer-approved; keeps the main thread on launch-critical code |

## The 3 days

**Day 1 (2026-07-02, rest of):**
- P2 slice 2 (TDD): configurable hard timeout in `_default_runner` (default well
  under 600 s; per-call override), usage-limit signature detection per provider
  (claude/codex/gemini/ollama) → `EngineLimitReached` with retry-after when parseable;
  jobs pause resumably (already do on EngineFailed); clear message. Hostile battery rows.
- Launch in background: 100k-note scale bench; negatives set expansion (6→30).
- Verify `talamus setup` e2e on this machine (claude-cli + ollama paths).

**Day 2 (2026-07-03):**
- `talamus import-vault <dir>`: markdown-vault importer (Obsidian flavor: frontmatter,
  `[[wikilinks]]`, folder → tags), services + CLI + one webapi endpoint; llm_wiki if
  format available. TDD, hostile inputs (broken frontmatter, circular links).
- Clean-venv cold install check (Windows here; Linux/macOS via CI).
- README + user docs pass (English, honest, the wedge up front).

**Day 3 (2026-07-04):**
- Integrate bench results (100k row in STATE; PRODUCT table refresh incl. stale rows).
- Demo script ("your agent remembers, free, in your language, in one command") +
  "own a word" messaging block.
- Release: version 1.0.0, changelog, `python -m build` + `twine check`, tag.
  **Publishing itself (PyPI/GitHub public) is Giovanni's call and click.**

## Owed to Giovanni (only what is truly his)

1. PyPI package name (`talamus` availability — reserve it early).
2. Public GitHub repo timing (simultaneous with PyPI?).
3. llm_wiki on-disk format access (else D3 ships md-vault only).
