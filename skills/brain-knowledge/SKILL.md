---
name: brain-knowledge
description: Use when answering questions against a local Brain knowledge project or when modifying rendered knowledge notes.
---

# Brain Knowledge Skill

Use this protocol when working with a Brain knowledge project.

## Core Rule

The graph is the primary index. It is not source truth.

Use the graph to decide which notes or normalized source sections to read. Then
answer from the real files with citations.

## Retrieval Order

1. Run `brain graph query "<question>"`.
2. Read selected final notes with `brain notes read <id-or-path>` or direct file reads.
3. Follow validated wikilinks when the selected notes point to necessary context.
4. If the graph is insufficient, run `brain search "<query>"`.
5. If final notes are insufficient, inspect normalized source sections.
6. Cite final notes and their precompiled source references.

## Authoring Rules

- Do not create broken wikilinks.
- Do not cite graph metadata as source truth.
- Do not copy raw source dumps into final notes.
- Preserve raw and normalized provenance.
- Use aliases, tags, and retrieval text to improve future routing.
