# P2 tiering — model resolution confirmed, cost delta

Confirms `talamus.routing.EngineRouter` resolves a materially different (cheaper) model
for `TaskClass.EXTRACTION` under the new `economy` default vs. the prior flat
single-model behavior, measured 2026-07-02 on the two providers with a subscription on
this machine:

```text
claude-cli  economy (new default)        -> haiku
claude-cli  quality (old flat behavior)  -> opus
codex-cli   extraction (economy/low)     -> gpt-5.4-mini, model_reasoning_effort=low
codex-cli   ask_answer (quality/high)    -> gpt-5.5,      model_reasoning_effort=high
```

Bulk extraction is the highest-volume call in the pipeline (one call per ~5k-token
chunk of every ingested document, plus one per file in a repo scan), so the economy
default lands exactly where the aggregate spend is. Of the ten task classes, seven run
economy (extraction, routing, query expansion, enrich, consolidate, both naming tasks)
and only the answer the user actually reads (`ask_answer`), session capture
(`session_remember`) and source verification (`verify`) pay for the quality tier.

Codex flags were re-smoke-tested live on 2026-07-02: `gpt-5.4-mini` + `low` and
`gpt-5.5` + `xhigh` both accepted and answered (codex effort supports
low/medium/high/xhigh; our two-axis low/high passes through verbatim and stays valid).

Full live-call cost/latency measurement (tokens actually billed, wall time per chunk)
is deferred: the model-resolution proof above is sufficient to confirm the mechanism
works, and the absolute dollar/token savings depend on each provider's published
per-model pricing, which changes independently of this codebase.
