# Design principles

Talamus makes a small number of deliberate, unusual choices. This page states
each one and why it exists, so you can decide whether the trade-offs fit you —
and so contributions don't accidentally undo them.

## 1. No embeddings

Anyone — including non-technical users — gets personal and agentic memory with
only the LLM they already have: a coding-agent subscription, or zero
subscriptions via a local model. No GPU, no vector database, no pay-per-call
embedding API, no hosted services.

Semantic power is bought differently: at **ingest** time it is written into the
notes by your own LLM (canonical aliases, bilingual retrieval text, symptom
phrasings), and at **ask** time your LLM expands the query into corpus
vocabulary. The "semantic bridge" is readable text inside the note, not an
opaque vector — you can see it and fix it.

Embeddings may one day exist as a strictly optional extra, but only if
measurements show the by-construction route has a real gap.

## 2. OS-agnostic and LLM-agnostic

Talamus runs on Linux, macOS and Windows, with any engine: the Claude, Codex,
Gemini, opencode or Antigravity CLIs, a local Ollama model, or an API key.
Cheap and weak models are first-class citizens: every code path that consumes
LLM output degrades gracefully on truncated, malformed, empty or prose-wrapped
answers — a dedicated hostile-model test battery enforces this in CI.

## 3. Python stdlib core; everything else optional

The core package has **zero dependencies**. Optional features live behind
extras (`ui`, `mcp`, `pdf`, `bench`, `docs`). A bare `pip install talamus`
gives you a fully working brain.

## 4. Your Markdown notes are the truth

`notes/*.md` is what you own and edit (Obsidian-compatible). The cache JSON
holds the machine record (provenance, relations, retrieval text). The graph,
search indexes, domain overview and federated index are **derived** — always
rebuildable with `talamus reindex`, never source truth. You can delete
`.talamus/cache/` at any time and lose nothing.

## 5. Answers read real notes and cite them

`talamus ask` answers only from real note content placed in context, cites
`[n]` with a sources legend, answers in the language of your question, and
says honestly when the brain does not know — it never invents.

## 6. No LLM spend without an estimate and your consent

Any multi-call operation (big-document ingest, enrichment, repository scan)
first prints a dry-run estimate (calls, tokens) and runs only with an explicit
`--yes`. You are never surprised by a bill or a burned rate limit.

## 7. Provenance, history and sources — always preserved

Every note carries source references (file, locator, content hash).
Corrections are **proposed** to a review queue, never silently applied. The
temporal model invalidates, never deletes: notes have version history, facts
have validity windows.

## 8. The ontology emerges from your notes

Relation types are not hand-defined. They are induced from evidence across the
brain, named by the LLM, versioned in a schema, and promoted only by measured
rules (support ≥ 8 across ≥ 3 distinct notes). The ontology clusters notes
into domains and domains into macro-areas — the brain builds its own table of
contents, which routes every question.

## 9. Three-layer language architecture

Prompts are always English (cheap models follow English best) with an output
language directive. Note prose is in **your** language. The machine layer is
English-canonical: every note carries an English canonical alias, bilingual
retrieval text, and English relation verbs — so cross-language search and a
consistent ontology work by construction, without embeddings.

## 10. Measured changes only

No retrieval or answer-quality change ships unless it wins measured ablations
on more than one real corpus, and every win gets a regression floor in CI (see
[Measuring retrieval](evaluation.md) and [Benchmarks](benchmarks.md)).
Negative results are kept on record so dead ends are not re-explored. Numbers,
not vibes.
