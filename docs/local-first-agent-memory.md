# Local-first memory for AI agents

AI agents are useful inside a session and forgetful between sessions. The
failure is rarely that the model cannot reason. The failure is that decisions,
constraints, evidence, and corrections disappear when the context window is
reset or a different tool takes over.

Agent memory should therefore be more than a transcript archive or a vector
search endpoint. It should be durable, inspectable, attributable to sources,
and safe to correct. A local-first design makes those properties available
without turning a hosted service into the owner of the user's knowledge.

This guide explains the design criteria behind Talamus and gives you a small,
no-LLM evaluation path so you can decide whether the trade-offs fit your
agents.

## What durable agent memory needs

| Requirement | Why it matters |
| --- | --- |
| A readable source of truth | People must be able to inspect, edit, diff, and back up memory without a proprietary client. |
| Source grounding | A remembered statement is only useful when an agent can show where it came from. |
| Time | The system must distinguish what is true now from what was believed earlier. |
| Reviewable corrections | An agent should propose changes, not silently rewrite shared knowledge. |
| Local retrieval | Routine search and recall should not require a cloud account or a paid inference call. |
| Explicit inference | Operations that use an LLM should be visible, estimated, and consented to. |

These requirements change the architecture. Memory is no longer a hidden
field attached to one assistant. It becomes a small knowledge system shared by
people and agents.

## The local-first shape

Talamus keeps the durable layer in ordinary Markdown. The search index,
knowledge graph, domain overview, and federated indexes are derived local
artifacts. If a derived cache is removed, `talamus reindex` rebuilds it from the
notes.

That separation creates a useful boundary:

1. Documents, repositories, URLs, and consented session captures enter the
   brain as source material.
2. The durable result is a set of linked Markdown concept notes with provenance.
3. SQLite/FTS5 provides fast local retrieval without an embedding service.
4. Agents receive the matching note content and citations, not an opaque score
   alone.
5. Corrections enter a review queue. Superseding a note closes its current
   validity while preserving the earlier version for `--as-of` queries.

The same brain can be opened in a text editor or Obsidian, queried through the
CLI, or exposed to Claude Code, Cursor, Codex, Gemini CLI, OpenCode, and other
MCP clients.

## Memory is not “load the whole folder”

Putting every note into the prompt works only while the corpus is small. It
also makes it difficult to show why a particular statement was used. A memory
layer should narrow the working set before generation and preserve the trail
back to the original note.

Talamus separates retrieval from answer generation:

- `search`, `recall`, `read`, `neighbors`, `history`, and `timeline` operate on
  local data;
- `ask` gives the selected, cited notes to the LLM engine chosen by the user;
- multi-call operations such as large ingests estimate their work before they
  run and require explicit confirmation.

This distinction matters for both privacy and cost. “Local-first” does not mean
that every optional model call is magically free. It means the core remains
useful without a hosted dependency, and inference is never smuggled into a
routine search operation.

## Why citations and time belong together

A citation answers “where did this come from?” Time answers “when was this the
active belief?” Agents need both.

Consider an architecture decision that changes from a remote vector database
to local FTS5. Deleting the old decision loses history. Keeping both decisions
active makes retrieval ambiguous. A bitemporal handover preserves the old note,
records when the new decision became valid, and lets current queries prefer the
successor while historical queries still reach the earlier state.

In Talamus, `supersede`, `history`, `timeline`, and `--as-of` expose that model
directly. The details are documented in the
[architecture guide](architecture.md).

## A five-minute evaluation without an LLM

Install the local core and MCP extra, create the built-in example brain, and
inspect it:

```bash
pipx install "talamus[mcp]"
talamus demo
talamus search "embedding"
talamus neighbors "Embedding"
talamus read "Embedding"
```

You can also reproduce the launch story without an API key or model call:

```bash
git clone https://github.com/ampres-ai/talamus
cd talamus
python scripts/demo/run_magic.py --fake
```

The fake path is deliberately part of the public demo. It lets you inspect the
capture, recall, citations, and fresh-session handoff before trusting an LLM or
spending anything.

To connect the real server to supported coding agents:

```bash
talamus setup
```

Setup initializes the brain, configures the selected engine, and proposes
agent integrations. Session capture is installed only after an explicit
choice.

## How to evaluate any agent-memory system

Before adopting a memory layer, try to answer these questions from the product
itself rather than its landing page:

- Can you open and edit the durable memory without the product running?
- Can a recalled claim point to a source you can inspect?
- Can you ask what the system knew at an earlier date?
- Can an agent propose a correction without silently applying it?
- Does ordinary search work when the network and LLM are unavailable?
- Can all derived indexes be rebuilt from the durable source of truth?
- Are benchmark inputs, commands, losses, and result artifacts available?
- Does the integration ask before enabling session capture or paid inference?

Talamus documents its answers in the [design principles](design-principles.md),
[architecture](architecture.md), and [measured benchmarks](benchmarks.md). The
benchmark page links each public number to a committed artifact and keeps the
known losses visible alongside the wins.

## The trade-offs

Local-first memory is not the best answer for every deployment.

- A hosted team knowledge service may be simpler when centralized sharing and
  administration matter more than local ownership.
- Talamus intentionally avoids embeddings in the core. Its semantic retrieval
  depends on readable retrieval text and the query-expansion engine you bring;
  the published benchmarks show where strong and weak engines differ.
- Plain files make ownership and recovery simple, but multi-writer
  synchronization remains the user's responsibility.
- Review gates improve safety at the cost of an extra step when knowledge
  changes.

Those are deliberate constraints, not invisible implementation details. The
right memory system is the one whose failure modes you can see and accept.

## Try it or inspect the implementation

Start with the [quickstart](quickstart.md), inspect the
[16 MCP tools](agent-tool-calling.md), or read the source on
[GitHub](https://github.com/ampres-ai/talamus). Talamus is Apache-2.0 and does
not require an account or hosted service for its local core.

If this is the kind of agent memory you want to see developed in public,
[star Talamus on GitHub](https://github.com/ampres-ai/talamus) so other builders
can find it.
