---
type: concept
tags: [decision-logging, observability, operational-hygiene]
sources:
  - AI Space/normalized/pdf/test-book.md#chapter-4-operational-hygiene
captured-at: 2026-05-22T16:30:25.045124+00:00
ingestion-run: 3022c130
---

# Decision Logging

Every ingestion run should produce a persistent record of its choices: which items were promoted to the wiki, which were skipped, and the reasoning behind each decision.

Without decision logs, diagnosing wiki staleness or missing content requires re-running the entire pipeline with debug flags. With them, an operator can grep a run ID and see exactly what happened.

Practical shape: a JSON-lines file per run (or a single append-only log) with fields like `source`, `action` (promoted / skipped / failed), `reason`, and `timestamp`. Store these alongside the wiki in version control or in a dedicated `logs/runs/` directory.
