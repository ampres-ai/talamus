# Security Policy

Talamus is **local-first**: your brain (notes, sources, indexes) lives on your
machine, under your project directory. Nothing is sent anywhere except to the
**LLM engine you configure** (e.g. your local `claude` CLI, a local Ollama model,
or an API you opt into).

## Threat model

A local-first tool defends against different adversaries than a service. The
ones we design against, in order of realism:

1. **A malicious website in your browser** trying to reach the local workbench
   on `127.0.0.1` (CSRF / DNS rebinding).
2. **Malicious content you ingest** — documents, vaults, scanned repositories
   (e.g. symlinks pointing at your SSH keys).
3. **A prompt-injected agent** driving the MCP write tools.
4. **A curious same-machine user** reading files your OS lets them read.

Out of scope: nation-state adversaries and physical access — a local tool
cannot defend the machine from its owner's attacker.

## What is closed (verified by tests in CI)

- **Workbench locked to its own UI** — the local FastAPI app requires a random
  per-launch UI token on every mutating request, rejects foreign
  `Origin`/`Referer` headers, and only accepts `127.0.0.1`/`localhost` hosts
  (TrustedHost). A DNS-rebinding page cannot read the token, so it cannot
  forge a request.
- **Symlink exfiltration blocked** — vault import and repository scan skip
  symlinked files and directories and require every resolved path to stay
  under the scanned root, so a vault containing `Notes.md -> ~/.ssh/id_ed25519`
  never gets the target read, copied, or sent to the LLM.
- **MCP path traversal blocked** — `ingest_text(name=...)` is slug-sanitized
  and containment-checked, so an injected agent cannot write outside the
  brain's raw directory with a crafted name.
- **Zip-slip blocked** — brain archive import rejects path-traversal entries
  before extraction.
- **Scan secrets gate** — repository scans detect likely secrets, redact them
  before any LLM call, and stop for explicit approval (`--allow-secrets`).

## Known debt (honest, tracked, non-blocking)

These are real and scheduled for the first releases after launch:

- **Credentials file permissions** — a key saved from the workbench Settings
  is written to `TALAMUS_HOME/credentials.json` in plaintext with default file
  permissions. Until it is created owner-only, prefer environment variables
  for engine credentials on shared machines.
- **MCP write tools are on by default** — `remember`, `ingest_text`,
  `propose_note` and the review tools are reachable by any agent connected to
  the server. A read-only default with an explicit `--enable-writes` (and a
  separate gate for central-brain writes) is planned.
- **Secret detection does not cover PDF/DOCX text** — secrets embedded in
  binary-document text are not yet flagged or redacted during scans.
- **YAML frontmatter escaping** — hostile characters in a note title can
  corrupt that note's frontmatter (no code execution; data-integrity only).

## Posture

- **No network by default.** The core does no network I/O. The only outbound
  calls are to the LLM engine you choose.
- **MCP exposure is local.** The MCP server runs over **stdio** by default. The
  optional HTTP transport binds to **`127.0.0.1`** (localhost) only — it is not
  exposed to your network or the internet.
- **No remote endpoint yet.** Exposing the brain to browser-based LLMs would
  require a remote endpoint; that is deliberately **out of scope** and, when
  built, will be **authenticated and read-only** (see [ROADMAP.md](ROADMAP.md)).
- **Engine CLIs run sandboxed.** codex runs with a read-only sandbox, gemini in
  plan mode — Talamus never loosens those flags.
- **Secrets.** Prefer environment variables for engine credentials; they are
  never written to notes or logs (see the known-debt note on
  `credentials.json` if you use the Settings UI instead).
- **Your data is yours.** Deleting the project directory deletes the brain.

## Reporting a vulnerability

Please open a [private GitHub security advisory](https://github.com/ampres-ai/talamus/security/advisories/new)
with steps to reproduce. Do not file public issues for security-sensitive
reports until a fix is available. Reports on the known-debt items above are
still welcome — severity may be higher than we assessed.
