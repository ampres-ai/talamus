# Agent Protocol

This workspace is a Dual Graph LLM Wiki for Forward Deployed AI Engineering.

## Roles

- `FDE Brain/` is the final Obsidian vault.
- `AI Space/` is the AI operating area.
- Claude Code is the scheduled pipeline runner.
- Codex is the manual development and maintenance agent.
- Both Claude Code and Codex can answer questions against the knowledge base.

## Non-Negotiable Rules

- Do not treat Graphify output as source truth.
- Use Graphify to find candidate files, then read the real Markdown files.
- Do not write generated Graphify Obsidian exports into `FDE Brain/`.
- Do not put drafts, temporary notes, or raw dumps in `FDE Brain/`.
- Every knowledge-base answer must cite sources.
- If a query uses `AI Space/normalized/`, promote stable/reusable knowledge into `FDE Brain/` in the same turn unless current user instructions explicitly forbid file changes.
- Current user instructions such as read-only, review-only, no edits, or no file changes override automatic promotion behavior.
- Current user instructions such as no commits override automatic commit behavior.
- Never permanently delete originals.
- Do not clean `AI Space/pending/` unless items were safely archived, reviewed, or failed.

## Retrieval Order

1. Query Brain Graph in `AI Space/graph/brain/`.
2. Read the relevant notes in `FDE Brain/`.
3. Answer with citations from the note and its precompiled sources.
4. If Brain Graph is insufficient, query Source Graph in `AI Space/graph/sources/`.
5. Read relevant files in `AI Space/normalized/`.
6. Answer with citations.
7. If file changes are allowed, promote stable/reusable knowledge into `FDE Brain/` before finishing the turn.
8. If a query uses `AI Space/normalized/` but file changes are forbidden, answer with citations and clearly state that promotion was skipped due to the current instruction; do not modify files or commit.
9. Update Brain Graph or mark it stale only after allowed ingestion or allowed promotion changes.
10. Log and commit only after allowed ingestion or allowed promotion changes, and only when commits are allowed.

## Citation Rules

Prefer the finest available locator:

- final note and heading
- normalized source file and heading, chapter, section, page, or line
- raw source and page or chapter
- URL and access date for web sources

If a locator is coarse, say so.

## FDE Brain Authoring

`FDE Brain/` must be Obsidian-native Markdown:

- use Properties/frontmatter
- use wikilinks
- use aliases
- use tags
- link to headings when useful
- keep provenance inside the note

Use `kepano/obsidian-skills@obsidian-markdown` as the authoring reference.
For Codex, the skill is installed as `obsidian-markdown`; restart Codex after installation if the skill is not visible in the active skill list.

## Graphify

Use two graphs:

- Brain Graph: `AI Space/graph/brain/`
- Source Graph: `AI Space/graph/sources/`

Preferred backend:

```powershell
graphify extract <input> --backend ollama --model gemma4:e4b --max-concurrency 1 --token-budget 12000 --api-timeout 1800 --out <output>
```

Manual Claude fallback is allowed only when explicitly requested:

```powershell
graphify extract <input> --backend claude --max-concurrency 1 --out <output>
```

## Review And Failure Routing

- Ambiguous content: `AI Space/review/ambiguous/`
- Conflicts: `AI Space/review/conflicts/`
- Human judgment needed: `AI Space/review/needs-human/`
- Low-confidence OCR or parsing: `AI Space/review/low-confidence-normalization/`
- Technical failures: `AI Space/failed/technical-failures/`

## Git

Commit after successful ingestion runs and query-driven promotions only when those ingestion or promotion changes were allowed and commits are allowed.

Use focused commit messages:

```text
chore(ai-pipeline): ingest pending batch YYYY-MM-DD
docs(fde-brain): promote source knowledge from query
chore(graph): refresh brain and source graphs
```
