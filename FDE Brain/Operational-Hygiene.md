---
type: chapter
tags: [operational-hygiene, pipeline-discipline, ingestion]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-4-operational-hygiene
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Operational Hygiene

Operational hygiene is the discipline of treating a knowledge-base pipeline as a production system rather than a hobby project. Five principles define it:

1. **Scheduled ingestion** â€” Run ingestion on a fixed cadence (cron, CI, or equivalent). Ad-hoc runs invite drift: sources get stale, duplicates creep in, and nobody notices until the wiki is unreliable. A schedule makes freshness a property of the system, not of someone's memory.

2. **Decision logging** â€” Every pipeline run should record what was promoted, what was skipped, and why. Logs are the audit trail that lets a future operator (or your future self) understand the current state of the graph without re-reading every source. Prefer structured logs (JSON lines, run manifests) over plain text.

3. **Failure routing** â€” Errors must never be silently swallowed. When extraction, normalization, or promotion fails, the item goes to a review queue. The queue is the contract between the automated pipeline and human judgment: the machine admits what it cannot handle, and a human resolves it on their own schedule.

4. **Git-as-backbone** â€” Treat the wiki as code. Every changeâ€”new notes, edits, graph snapshotsâ€”lives in version control. This gives you rollback, blame, diff, and branch-based review for free. The graph snapshot committed alongside content means you can reconstruct the full state of the wiki at any point in history.

5. **Quarterly review** â€” Walk the `review/needs-human` queue at least once per quarter. Decide each entry: promote, discard, or refine. This ceremony prevents the queue from becoming a graveyard and keeps human oversight proportional to pipeline volume.
