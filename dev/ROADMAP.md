# Talamus — The Legacy Roadmap

> **This document is written for the models who will inherit this project.**
> It was authored on 2026-07-02 by a stronger model that will soon be gone,
> for successors who write code superbly but reason and strategize less well.
> **So this document carries the thinking, not the typing.** Where you see a
> decision, the *reasoning and the consequences* are spelled out — do not
> re-litigate them; execute them. Where you see a task, it is atomic and has an
> acceptance test — implement it and prove it. When something genuinely new
> appears that this document does not cover, **stop and ask Giovanni**, laying
> out the consequences of each option, exactly as this document was built.

---

## 0. How to use this document (read this first, every time)

### 0.1 The division of labor

You (the successor model) are excellent at writing correct code and following a
precise spec. You are weaker at: choosing what to build, resisting scope creep,
spotting when a "small" choice has large consequences, and keeping the strategic
line coherent across weeks. **This document is your strategic brain.** Trust it
over your own improvisation. The order of the phases is not arbitrary — it is the
critical path to a launch that does not embarrass us.

### 0.2 The prime directives (never violate these)

1. **Green gate before every commit.** `python dev.py` must end `ALL GREEN`
   (ruff + ruff format + mypy + unittest). A red gate is never committed. In a
   worktree, run with `PYTHONPATH=<worktree>/src` or you test main's code, not
   yours (this has bitten us — see [worktree gotcha](#a3-known-traps)).
2. **TDD.** Write the failing test first, watch it fail, implement, watch it pass.
   Every behavior change ships with the test that proves it.
3. **The services seam is law.** CLI, MCP, and the web UI call `services/` only —
   never core modules directly. This is why one feature serves all three consumers
   at once. Adding a feature = add a service function, then thin adapters in each
   interface.
4. **The graph and every index are derived, never truth.** Truth is the notes +
   their provenance. Anything in `.talamus/cache/` can be deleted and rebuilt with
   `talamus reindex`.
5. **The two-corpora law.** No retrieval/quality change ships unless it wins
   measured ablations on the real corpora (book + docs + garden), with negatives
   recorded and CI floors that lock the win. Numbers, not vibes.
6. **Honesty in claims.** Every number in a doc or in public copy must exist in
   `dev/STATE.md` or `benchmarks/results/`. Never claim a capability you have not
   measured. If you cannot verify a thing (e.g. a CLI flag on an engine not
   installed here), do not ship it as working — say so.
7. **Free-first / €0 / local.** The core never requires a paid API key, a cloud
   account, or embedding infrastructure. Power-ups for the paying user come after
   launch and may never weaken the free core.

### 0.3 How to delegate to codex (do this constantly — it is how we parallelize)

Codex is a capable coding CLI on this machine. Use it for well-bounded,
mechanical, or clearly-specified work while you keep the strategic thread. It runs
in the background; you supervise and finalize.

```bash
# read-only analysis / audits (no writes):
codex exec --skip-git-repo-check -s read-only -m gpt-5.5 -c model_reasoning_effort=high - <<'EOF'
<a precise, self-contained prompt with acceptance criteria>
EOF

# write tasks — ALWAYS in a dedicated git worktree, never on main:
git worktree add C:/dev/_codex_<task> -b feat/<task> main
cd C:/dev/_codex_<task>
codex exec --skip-git-repo-check -s workspace-write -m gpt-5.5 -c model_reasoning_effort=high - <<'EOF'
<the task, with: files to touch, the exact behavior, the tests to add,
 and "run: PYTHONPATH=<worktree>/src python dev.py — must be ALL GREEN">
EOF
```

**Codex sandbox truths you must know (learned the hard way):**
- Its sandbox **cannot delete files or run `git add`/commit**, and **cannot write
  temp dirs under the user profile**, so `python dev.py` fails inside it on the
  unittest stage. Have codex do the *edits and the targeted test runs*
  (`python -m unittest tests.test_x`), then **you** do the deletions, the full
  gate, and the commit/merge from the real checkout.
- Models: `gpt-5.5` (flagship; `-c model_reasoning_effort=high|xhigh` for hard
  problems), `gpt-5.4-mini` (fast/cheap for mechanical work).
- `agy -p "<prompt>"` (Antigravity) is a second background worker; prompt on stdin
  works too. `gemini` CLI is dead on this machine — do not use it as a worker.

**What to delegate vs keep:** delegate mechanical refactors, test scaffolding,
audits, doc sweeps, format/lint fixups. Keep for yourself: the strategy, the
architecture decisions, the security-sensitive code, and anything that needs
judgment about the product.

### 0.4 The task format used throughout

Each task below is: **[ID] Title** — *why (which decision it serves)* — the work —
**Accept:** the concrete acceptance test — **Delegate:** yes/no + to what.

---

## 1. What Talamus is (the one breath)

**Talamus is the local-first memory your AI agent already has.** It compiles what
you read, write, and work on into source-grounded, cross-linked, cited concept
notes — a second brain that both you and your agents share, powered entirely by
the LLM you already pay for (a €20 coding-agent subscription) or a free local
model (ollama). No cloud, no embeddings, no API key required.

Three things nobody else has together:
- **TIME** — bitemporal: notes have version history, facts have validity windows,
  corrections invalidate instead of deleting, `ask --as-of` answers from the past.
- **MEANING** — a self-emerging ontology: relation types are induced from evidence,
  named, versioned, promoted by measured rules — and now shared across every brain.
- **VERIFIABILITY** — active provenance: every note knows its sources; `verify`
  re-checks notes against them and proposes corrections; answers cite.

---

## 2. The strategic spine — the launch decisions (2026-07-02)

These were ruled by Giovanni after weighing the consequences. **They are settled.**
They resolve the real tensions between his five priorities (UX, power, extreme
accessibility, absurd performance, magic→virality). Every phase below traces to one.

| # | Decision | The reasoning you must not forget |
|---|---|---|
| **D1** | **Launch publicly, soon** — order the roadmap so what makes the launch *credible* comes first, then iterate in public. | A solo builder learns nothing from building in the dark. Real feedback beats a hypothetically-perfect private build. But "soon" ≠ "raw": the launch must not waste the first impression. |
| **D2** | **Developer-first magic** — the wow is *"your agent remembers across sessions, €0, local."* Invest in MCP + the capture hook + cost-frugality first. Human UX second (not neglected). | This is the category we can own that competitors can't copy (they bolted agent-access onto a human wiki; we are agent-native from the core). The developer audience (r/LocalLLaMA, HN) is reachable, vocal, and viral. |
| **D3** | **Accessibility floor = "any one LLM"** (a subscription CLI *or* ollama). We do NOT build a free-cloud path. **But opencode must be configured and connected cleanly in onboarding** — through it a user reaches free/cheap models they set up. | Serving "someone with literally nothing" would blur the €0/local dogma and open ToS/reliability cans of worms. The honest floor is "you have one LLM." opencode is the pressure valve for the truly-broke: it can point at free tiers without us owning that path. |
| **D4** | **Defer the embeddings decision** — keep the core embedding-free now; decide post-launch with data on the corpora. | A strong dense model beats us on *pure* cross-language retrieval (RS7). But embeddings cost the €0/local/inspectable thesis. We do not pay that price on a hunch — we measure first, and only ever as an opt-in power-up. |
| **D5** | **Security: block launch only on critical+high**; ship the rest immediately after. | The audit found a real critical (localhost workbench has no CSRF/DNS-rebinding defense) + symlink exfiltration + MCP path traversal. Those must be closed before a public repo. The medium/low (credentials 0600, YAML-escape, MCP read-only default) are debt we pay down in the first days, not launch blockers. |
| **D6** | **Hook: automatic with initial consent** — setup proposes it, explains exactly what it captures and where it goes, the user accepts once; then the agent remembers on its own (worth-remembering gate + audit log). | Full-auto without consent is a privacy landmine that kills virality the moment one person is surprised by it. Pure opt-in kills the "it just remembers" magic. Consent-once is the equilibrium. |
| **D7** | **All three wow proofs are required pre-launch** — (1) the 60-second end-to-end demo, (2) frictionless MCP install across agents, (3) the killer benchmark. | The demo is the *emotion*, the install is the *reproducibility* (the wow must survive the viewer trying it), the benchmark is the *argument* for the skeptical first HN comment. One without the others fails. |

---

## 3. Honest current state (what is real, what is fragile)

**Built and solid (gate-green, ~600 tests):**
- The full loop: ingest (files/URLs/folders/repos/sessions) → LLM extracts cited
  concept notes → graph + sqlite-fts5 index + emergent ontology → routed cited
  answers. Measured: ask hit@8 **0.972**, `search --smart` **0.972** book /
  **0.782** docs, plain search ~0.86.
- **Per-task engine tiering** (`talamus/routing.py`, `EngineRouter`): every LLM
  call resolves model+effort by task class; bulk→cheap, answers→strong. Config
  `task_tiers`/`provider_models`. Usage-limit detection + `TALAMUS_ENGINE_TIMEOUT`.
- **Engines:** claude-cli, codex-cli, gemini-cli, **opencode**, **antigravity-cli**,
  ollama, anthropic-api — the CLI ones live-verified through the router.
- **Global ontology** (2026-07-02): one learned schema across all brains under
  `TALAMUS_HOME/ontology/`, per-brain opt-out, auto-migration.
- **MCP:** read tools + the moat tools (`ask` cited, `verify`, `read_note --as-of`)
  + write tools (remember/ingest_text/propose/review).
- **Web workbench (React):** 9 views, brain switching, d3 graph, Aurora identity;
  `talamus ui` launches it (pywebview window / `--web` browser); the inspector has
  the **time-travel (as-of)** and **verify** moat panels. Flet fully retired.
- **Migration:** `talamus import-vault` (Obsidian/Notion markdown, 1:1, zero LLM).
- **Packaging:** `pip install`, `[ui]` extra, wheel ships the SPA. (v1.0.0 was built
  but is now **stale** — the ontology + engine changes landed after; rebuild at launch.)
- **Scale:** search p95 **72 ms** @ 10k, p50 **624 ms** @ 100k (usable, index 208 MB).

**Fragile or missing (this is the work ahead):**
- **Security** — the audit findings (§ Phase S). The critical (workbench CSRF/DNS
  rebinding) is a genuine launch blocker.
- **The magic is unproven end-to-end** — we have never demonstrated, in one take,
  an agent working on a project and then, in a *fresh* session, recalling and
  citing what it learned. Until that is real and smooth, D2 is a promise, not a fact.
- **MCP install friction** — not verified frictionless across Claude Code / Cursor /
  Codex. If a viewer can't reproduce the demo in one command, the wow dies.
- **opencode onboarding** — the engine adapter exists, but setup does not yet guide
  a user to configure/connect opencode (D3 requires this).
- **Performance is "usable," not "absurd"** — 624 ms @ 100k is fine, not a jaw-drop.
  D-priority "absurd performance" wants a front here.
- **Dead code / clean-code** — a code-health audit was launched but did not finish;
  it must be re-run and acted on (§ Phase C). Known suspects: `services/library.py`
  wiring, SDK `recall.py` usage, leftover helpers.
- **Docs drift** — README/STATE still say "11 views" (it's 9), the engine list in
  places is stale; a sweep is needed (§ Phase C).

---

## 4. What "publishable" means now (the launch bar, developer-first)

Launch = a public repo + PyPI `talamus` that a developer can `pipx install`, point
at their agent, and within minutes experience the wow — safely. Concretely, ALL of:

- **Security:** every critical+high audit finding closed (Phase S). A `SECURITY.md`
  documents the threat model and the remaining known medium/low debt honestly.
- **The magic works and is smooth:** the 60-second end-to-end recall demo is real,
  reproducible, and recorded (D7.1).
- **MCP installs in one command** on Claude Code, Cursor, and Codex, and the hook
  is proposed-with-consent (D6, D7.2).
- **The killer benchmark** is committed and reproducible, with a one-paragraph
  honest write-up including where we *lose* (D7.3).
- **Onboarding is frictionless for the floor user:** `talamus setup` detects the
  engine (incl. guiding opencode), installs the MCP + hook, reaches a cited first
  answer in minutes, on a modest PC (D3).
- **The gate is green, a cold `pip install` works, CI is green on 3 OSes**, docs
  match behavior, `talamus --version` is 1.0.0.

Everything else — embeddings, kimi, packaged desktop binary, chrome i18n, team
features — is explicitly **post-launch**.

---

## 5. The phases, in execution order

> Do them roughly in order; within a phase, tasks are mostly independent and many
> are delegable to codex. Each phase ends green and updates `dev/STATE.md`.

### Phase S — Security hardening · serves D5 (LAUNCH-BLOCKING for critical+high)

**Threat model (state it, then defend it).** Talamus is local-first, so the real
adversaries are: (1) a **malicious website** in the victim's browser reaching the
no-auth workbench on `127.0.0.1`; (2) **malicious content** we ingest — documents,
vaults, scanned repos; (3) a **prompt-injected agent** driving the MCP write tools;
(4) a **curious same-machine user**. Out of scope: nation-state adversaries and
physical access — a local tool cannot defend the machine from its owner's attacker.
The audit (§ A1) found one critical, three high, and several medium/low against
this model. Per **D5**, the critical+high are launch blockers; the medium/low are
paid down in the first days after launch, not before. That split is the two
subsections below.

#### LAUNCH-BLOCKING (critical + high — close before the repo is public)

- **[S1] Lock the workbench to the local UI (origin + token + TrustedHost).**
  *Why: the critical. The FastAPI app on `127.0.0.1` (`webapi/app.py`,
  `webapi/__main__.py`) has no auth and no Host/Origin check, so a page on
  `evil.test` that resolves its own hostname to `127.0.0.1` (DNS rebinding) becomes
  same-origin to the workbench and can POST JSON to every endpoint from the
  victim's browser. Serves D5.* Three layers, all required: **(a)** `TrustedHostMiddleware`
  allowing only `127.0.0.1`/`localhost`; **(b)** on every mutating (`POST`)
  endpoint, reject a request whose `Origin`/`Referer` is a real remote site;
  **(c)** mint a **random per-launch UI token** in the launcher, inject it into the
  served `index.html`, and require it on every `POST` — a foreign page cannot read
  a same-origin-only response, so it cannot forge the header.

  ```python
  # webapi/app.py — in create_app(), before the routes
  import os, secrets
  from starlette.middleware.trustedhost import TrustedHostMiddleware
  from fastapi import Header, HTTPException, Depends

  UI_TOKEN = os.environ.get("TALAMUS_UI_TOKEN") or secrets.token_urlsafe(32)
  app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

  def require_ui(request: Request, x_talamus_ui: str = Header(default="")) -> None:
      origin = request.headers.get("origin") or request.headers.get("referer") or ""
      if origin and not origin.startswith(("http://127.0.0.1", "http://localhost")):
          raise HTTPException(403, "cross-origin request rejected")
      if not secrets.compare_digest(x_talamus_ui, UI_TOKEN):
          raise HTTPException(403, "missing or bad UI token")
  ```

  Apply `dependencies=[Depends(require_ui)]` to every `@app.post(...)`. The launcher
  (`webapi/__main__.py`) generates the token (or reads `TALAMUS_UI_TOKEN`) and
  either substitutes it into the served `index.html` or exposes it on a GET the
  same-origin SPA reads and a cross-origin page cannot (CORS defaults block the
  read); the SPA then sends it as `X-Talamus-UI` on every write.
  **Accept:** a test starts the app, and (1) a `POST` with no token → 403; (2) a
  `POST` with the correct token → 200; (3) a `POST` with `Host: evil.test` → 400
  (TrustedHost); (4) a `POST` with `Origin: https://evil.test` → 403. Equivalently
  by `curl`: a spoofed-Origin or tokenless POST is rejected, the SPA's own POST is
  accepted. **Delegate:** you design the token handshake (where it is minted,
  injected, and read — this is the judgment call); codex implements the middleware,
  the dependency, and the tests.

- **[S2] Gate the path-taking web endpoints. → RESOLVED BY S1 (2026-07-02).**
  *Why it was high:* the arbitrary-path endpoints (`/api/active`, `/api/brains/init`,
  `/api/import/*`, `/api/scan/*`) let a *rebinding attacker* read local files into the
  LLM or init a brain in a sensitive dir. **S1 closes that vector entirely** — every
  `/api/*` call now needs the per-launch token that only the served SPA can read, and
  TrustedHost + the Origin check reject the rebinding request before it lands. The
  only remaining caller of these endpoints is the user's own workbench, and "open or
  create a brain in any folder" is an *intended* feature (Obsidian-vault style, D2/UX)
  — adding path restrictions there would be friction, not security. Decision (an
  orchestrator judgment call the roadmap authorizes): **do not restrict the paths;
  the S1 token is the correct fix.** If a *same-origin XSS* is ever found (none today —
  the SPA renders notes as escaped text), revisit. **Accept:** the S1 tests already
  prove every `/api/*` is refused without the token. **Delegate:** n/a — done.

- **[S3] Stop symlink exfiltration in vault-import and scan.** *Why: high. An
  untrusted vault or repo containing `Notes.md -> C:/Users/alice/.ssh/id_ed25519`
  (or a symlinked directory) gets the target read and copied into the brain / sent
  to the LLM. `vault_import.py` discovers with `rglob("*.md")` then `read_text` +
  `shutil.copyfile`; `scan.py` walks with `os.walk` and checks secrets by link name.
  Serves D5.* Skip symlinked files **and** dirs, require the resolved path to stay
  under the root, and run the secret-file check on **both** the link name and the
  resolved target.

  ```python
  # shared guard — reuse in _vault_files() and the scan walk
  def _safe_under(root: Path, path: Path) -> bool:
      if path.is_symlink():
          return False
      try:
          path.resolve(strict=True).relative_to(root.resolve())
      except (ValueError, OSError):
          return False
      return True
  ```

  In `vault_import._vault_files`, drop any file where `_safe_under(vault, path)` is
  false; in `scan.build_plan`, prune symlinked entries from both `dirnames` and
  `filenames` (a symlinked dir is a walk trap too) and run `is_secret_file` on the
  resolved target as well as the name. **Accept:** a test builds a temp vault/repo
  with a `.md` symlink pointing outside the root, runs import and scan, and asserts
  the target's bytes are never read or copied and the symlink is reported skipped;
  a symlink whose name looks secret-like is still excluded. **Delegate:** yes —
  codex; give it the guard above.

- **[S4] Sanitize the MCP `ingest_text(name=...)` path.** *Why: medium by CVSS but
  **treated as launch-blocking because it is agent-reachable** — a prompt-injected
  agent calls `ingest_text("x", name="../../notes/Pwned")` and the raw write at
  `ingest.py:323` (`raw_path = paths.raw / f"{name}-{digest}.md"`) escapes
  `.talamus/raw/`. Serves D5.* Sanitize `name` through the existing `note_slug`
  (already in `naming.py`) before it reaches the path, **and** assert containment
  before writing:

  ```python
  # ingest.py, ingest_text(...) — before writing
  from talamus.naming import note_slug
  safe = note_slug(name)
  raw_path = paths.raw / f"{safe}-{digest}.md"
  if raw_path.resolve().parent != paths.raw.resolve():  # defense in depth
      raise ValueError("raw path escapes the raw directory")
  ```

  (`note_slug` already strips `/`, `\`, and control chars, so `..`-traversal
  collapses; the assertion catches anything the slug misses.) **Accept:** a test
  calls `ingest_text(paths, "x", router, name="../../notes/Pwned")` and asserts the
  written file resolves inside `paths.raw`; a unit test asserts `note_slug` on the
  same input contains no separators. **Delegate:** yes — codex; reuse `naming.py`.

#### First days after launch (medium + low — non-blocking under D5)

Ship these in the first days, tracked in `SECURITY.md` as known debt until closed.

- **[S5] Credentials file created owner-only.** *Why: medium. `save_credential`
  (`adapters/llm.py`) writes `TALAMUS_HOME/credentials.json` in plaintext with
  default perms, readable by other same-machine users.* Create it `0o600` on POSIX
  / owner-only ACL on Windows; prefer OS credential storage where available.
  **Accept:** a test asserts the file's mode is owner-only after `save_credential`.
  **Delegate:** yes.

- **[S6] MCP read-only by default; explicit write + central gates.** *Why: medium.
  Every MCP write tool (`remember`, `ingest_text`, `propose_note`, `review_*`) and
  `scope="central"` is reachable by a prompt-injected agent.* Default the server to
  **read-only**, add an explicit `--enable-writes`, and a **separate** gate for
  central-scope writes (not implied by `--enable-writes`). **Accept:** a test asserts
  the write tools refuse without `--enable-writes`, and a central-scope write refuses
  without the central gate. **Delegate:** yes.

- **[S7] Scan secret-detection must cover PDF/DOCX text.** *Why: medium. Both phases
  read with `read_text` and skip `.pdf`/`.docx` (`scan.py` line 214 in the plan,
  and the `handle` body in `execute_plan`), so secrets embedded in extracted
  document text are never flagged or redacted.* Run `find_secrets`/`redact` over
  `extract_text(...)` output for docs in **both** planning and execution. **Accept:**
  a test with a secret embedded in a `.docx`/`.pdf` fixture asserts it is flagged in
  the plan and redacted before the LLM call. **Delegate:** yes.

- **[S8] Emit YAML-safe frontmatter.** *Why: low. `storage/obsidian.py` emits
  `title:`, aliases, tags, and source fields unquoted (`f"title: {note.title}"`,
  `_yaml_list`), so a title containing `:`, a leading `-`/`#`, `{}`/`[]`, `---`, or a
  newline corrupts the note's frontmatter (and could inject keys).* Emit quoted,
  escaped scalars/lists (escape `\n`, `:`, leading `-`/`#`, `{}`/`[]`, `---`).
  **Accept:** a test round-trips a note whose title/tags contain each hostile
  character and asserts the emitted frontmatter parses back to the original values.
  **Delegate:** yes.

**SECURITY.md is part of the launch (§ 4).** Ship a `SECURITY.md` that states the
threat model above, records that S1–S4 are closed, lists S5–S8 as honest known debt
with target dates, and gives a private disclosure channel. It is referenced by the
launch bar (§ 4) and the launch assets (L3) — do not launch without it.

### Phase M — The Magic (developer wow) · serves D2, D6, D7

**Goal:** make "your agent remembers across sessions, by itself, €0, local" a real,
smooth, demonstrable experience — the single most important thing for virality.

- **[M1] Prove the end-to-end recall loop.** *Why: D7.1 — the emotion.* Build a
  scripted, reproducible scenario: (a) `talamus setup` in a fresh project; (b) an
  agent session that does real work and ends, firing the capture hook; (c) a
  **new** session where the agent, via MCP `recall`/`ask`, retrieves and cites what
  the previous session learned. Script it under `scripts/demo/` so it is
  re-runnable and CI-smoke-able (with a fake engine) and hand-runnable (with a real
  one). **Accept:** `scripts/demo/run_magic.sh` (or `.py`) runs the whole arc; a
  test asserts the second session's answer cites a note created from the first.
  **Delegate:** partial — you design the arc; codex writes the harness + test.

- **[M2] Make the capture hook consent-first and legible. → DONE (2026-07-07).**
  `talamus setup` now shows the full consent copy (transcript + git diff, the
  worth-remembering gate, THIS brain as destination, the `.talamus/logs/capture.log`
  audit trail), asks once (`--capture ask|yes|no`, default ask; non-interactive or
  EOF ⇒ no), and writes the hook into `.claude/settings.json` only on yes via
  `services.integrations.install_capture_hook` (merge-not-clobber, idempotent).
  `talamus hook --install` is the explicit later-consent path. Hook command now
  quotes the root (paths with spaces). Tests: `tests/test_talamus_hook_consent.py`
  covers the acceptance exactly.

- **[M3] Measure and tighten capture quality.** *Why: D2 — the magic must be
  *good*, not just present.* On real sessions, measure how good the extracted notes
  are (do they capture the decision + the why?). Tune the `remember_session` prompt
  and the worth-remembering gate. **Accept:** a small judged set under
  `benchmarks/ask_eval/` for session-capture quality, with a recorded number and a
  FAST floor. **Delegate:** yes for the harness; you judge the prompt quality.

- **[M4] Context-frugality as a headline, measured.** *Why: D2 — "doesn't burn your
  limits."* Ensure `recall`/`ask` return the *minimum* context, and surface the
  token cost per answer (`ask --trace` already has the data; expose it in the MCP
  and UI). **Accept:** the token-recall benchmark (already ~−97.7% vs load-all) is
  re-run and shown to the user in `ask --trace` and the workbench. **Delegate:** yes.

### Phase A — Accessibility & onboarding · serves D3

**Goal:** anyone with one LLM reaches a cited first answer in minutes, on a modest PC.

- **[A1] opencode onboarding.** *Why: D3 — the pressure valve for the broke.*
  `talamus setup` detects opencode, and if chosen, guides configuring/connecting it
  (which provider/model, where its auth lives), verifying with a live one-word
  completion before declaring success. **Accept:** on a machine with opencode,
  `talamus setup --engine opencode` ends with a verified working engine or a clear,
  actionable error. **Delegate:** yes; you verify live.

- **[A2] The modest-PC path.** *Why: D3 + "runs everywhere."* Document and default
  a small-model ollama configuration; ensure the hostile-model robustness holds on a
  tiny quantized model; make sure `TALAMUS_ENGINE_TIMEOUT` and graceful degradation
  cover the slow-local case. **Accept:** a documented tiny-model config, and the
  hostile-model battery green including tier/effort args. **Delegate:** yes.

- **[A3] Setup is a joy, not a form.** *Why: D2/D3 — first impression.* Audit the
  `talamus setup` flow end-to-end for clarity: every step says what it does, why,
  and the cost (zero here). No dead ends. **Accept:** a fresh-machine run reaches a
  cited answer with no confusion; a doctor check catches every misconfig with a fix
  hint. **Delegate:** partial.

### Phase U — UX & the visible moats · serves UX priority, D2 (secondary)

**Goal:** the workbench is lovable and *shows* the superpowers. It is secondary to
the developer magic but must not look unfinished at launch.

- **[U1] A design pass on the 9 views.** *Why: UX priority.* Use the design skills.
  Consistency, hierarchy, motion, empty states, error states. The graph is the hero —
  it must feel alive and fast at any size. **Accept:** maintainer visual sign-off
  (this needs Giovanni's eye — schedule it). **Delegate:** partial; you drive taste.
- **[U2] The moats are already visible** (as-of + verify in the inspector, done
  2026-07-02) — extend to ontology insights (surprising links, gaps) and the token
  cost per answer. **Accept:** each moat has a visible, demoable surface.
- **[U3] Command palette (⌘K) + keyboard flow** for the developer who lives on the
  keyboard. **Accept:** every primary action reachable without the mouse. **Delegate:** yes.

### Phase P — Absurd performance · serves the performance priority

**Goal:** performance that makes people screenshot it. 624 ms @ 100k is not that yet.

- **[P1] Profile the 100k path and kill the dominant cost.** *Why: "assurde"
  performance is a stated priority and a viral proof.* Find where the 624 ms goes
  (query expansion? ranking? note loads?) and cut it hard. Target sub-100 ms @ 100k
  for plain search. **Accept:** a re-run `benchmarks/results/` artifact showing the
  new number; CI floor updated. **Delegate:** yes for the profiling harness; you
  choose the optimization.
- **[P2] Cold-start and memory footprint on a modest PC.** Measure RAM and cold
  first-answer time; bound them. **Accept:** documented numbers on a modest config.
  **Delegate:** yes.

### Phase B — The killer benchmark (the argument) · serves D7.3

**Goal:** a single, reproducible, honest proof for the skeptical first commenter.

- **[B1] The one-screen benchmark.** *Why: D7.3.* Assemble: tokens-per-answer
  (−97.7%), cited & grounded, €0 marginal, cross-language win (book hit 0.971 vs
  vector-DB 0.743), AND the honest loss (monolingual nDCG vs multilingual-e5, RS7).
  One command reproduces it; one paragraph explains it. **Accept:**
  `benchmarks/run.py` produces the table; a doc renders it; every number traces to
  an artifact. **Delegate:** yes.

### Phase C — Code health & docs truth · serves maintainability for the successors

**Goal:** the codebase the successor models inherit is clean, dead-code-free, and
its docs match reality. **This directly serves you, the inheritor.**

- **[C1] Finish the code-health audit and act on it.** *Why: a re-run of the audit
  that was interrupted.* Re-run the codex code-health audit (prompt in
  `scratchpad/` history), get the dead-code + clean-code tables, and execute the
  top-10 cleanups. Known suspects: `services/library.py` wiring, SDK `recall.py`,
  leftover `ui/` beyond `physics.py`, duplicated JSON-salvage parsers, any
  `_canonical_provider` copies. **Accept:** dead code removed with its tests; gate
  green; a short report in `dev/`. **Delegate:** yes — this is codex's sweet spot.
- **[C2] Docs truth sweep.** README/STATE/PRODUCT/quickstart match behavior: "9
  views" not 11, the full engine list, `talamus ui` = web workbench, import-vault
  present. **Accept:** `mkdocs build --strict` clean; a grep for stale claims is
  empty. **Delegate:** yes.
- **[C3] Repo hygiene** (mostly done 2026-07-02: `.gitignore` covers `.uidemo/`,
  `*_server.log`, `webui/node_modules/`). Verify no build artifacts or brains are
  tracked. **Accept:** `git ls-files` has no junk. **Delegate:** no (quick).

### Phase L — Launch mechanics · serves D1

**Goal:** ship, safely, reproducibly.

- **[L1] Rebuild v1.0.0** after Phases S/M land (the earlier build is stale).
  `python -m build` + `twine check` PASS; the wheel ships the current SPA.
- **[L2] Cold install matrix:** clean venv on this machine + CI green on
  Linux/macOS/Windows. **Accept:** documented pass.
- **[L3] Launch assets:** the recorded 60-second demo (M1), the messaging
  (`dev/plans/2026-07-02-launch-messaging.md`), `SECURITY.md`, `CHANGELOG` at 1.0.0.
- **[L4] The publish itself is Giovanni's click** — PyPI upload + git tag + making
  the repo public. Prepare everything; do not push the button.

### Post-launch backlog (do NOT do before launch)

- **Embeddings decision** (D4) — measure on the corpora, then decide opt-in local
  embeddings vs stay pure. - **kimi-cli adapter** (not installed here; verify flags
  when available). - **anthropic-api effort/thinking-budget.** - **Packaged desktop
  binary** (PyInstaller). - **Chrome i18n.** - **Cross-brain ontology support
  aggregation.** - **P3 ingestion:** docling/OCR opt-in extras, raw-prune with
  verify-lite, the ingest-quality benchmark. - **Team/shared brains.**

---

## 6. The delegation playbook (concrete recipes)

**When you pick up a task, ask: "is this mechanical or strategic?"**
- *Mechanical* (a refactor with a clear target, test scaffolding, an audit, a doc
  sweep, a format fix): **delegate to codex** with a self-contained prompt that
  includes the files, the exact behavior, the tests to add, and the acceptance
  command. Then finalize (delete/gate/commit) yourself.
- *Strategic* (a product choice, an architecture change, security-sensitive code, a
  UX taste call): **do it yourself**, and if it touches a settled decision or opens
  a new one, **ask Giovanni** with consequences laid out.

**The worktree dance (for any codex write task):**
1. `git worktree add C:/dev/_codex_<task> -b feat/<task> main`
2. codex works there (`-s workspace-write`), runs targeted `python -m unittest`.
3. You: review the diff, do any deletions codex couldn't, run the FULL gate with
   `PYTHONPATH=<worktree>/src python dev.py`, commit, `git merge --no-ff` to main,
   `git worktree remove`, delete the branch.

**Parallelism:** you can run 2–3 codex/agy jobs at once (e.g. security fix in one
worktree, doc sweep read-only, benchmark harness in another). Keep them on
*independent* files to avoid merge pain.

---

## 7. Appendix

### A1. The security audit (2026-07-02)

Full findings in `scratchpad/audit_security.txt` (and summarized in Phase S). One
critical (workbench CSRF/DNS-rebinding), three high (symlink exfil in vault-import
and scan, arbitrary-path web endpoints), several medium/low. Clean: no zip-slip
(backup import is guarded), no `shell=True`, no `dangerouslySetInnerHTML` in the
SPA (notes render as escaped text in `<pre>`).

### A2. The measured numbers (source of truth: `dev/STATE.md`)

ask hit@8 0.972 · search --smart 0.972 book / 0.782 docs · plain search ~0.86 ·
search p95 72 ms @ 10k, p50 624 ms @ 100k · refusal 1.000 (cloud+local) · token
recall −97.7% vs load-all · fully-local (gemma) correctness 0.800 €0.

### A3. Known traps

- **Editable install points at main's `src`.** In a worktree, always
  `PYTHONPATH=<worktree>/src` or `dev.py` tests the wrong code.
- **Codex sandbox** can't delete files, `git add`, or write user-profile temp dirs;
  the full `dev.py` fails inside it — run targeted tests there, full gate outside.
- **`dev.py` exports a temp `TALAMUS_HOME`** for hermetic tests (the global ontology
  is machine-wide) — schema-writing tests must isolate their own home.
- **CRLF on Windows** — git warns on line endings; harmless, ignore.

### A4. The canon (read these; this roadmap complements, does not replace them)

`AGENTS.md` (entry point) → `dev/CONSTRAINTS.md` (binding rules) →
`dev/ARCHITECTURE.md` (how it works) → `dev/STATE.md` (what's built/measured/
rejected — keep it current) → `dev/PRODUCT.md` (the finished-product bar). When
this roadmap and the canon disagree, the canon's governance wins; update both in
the same change.
