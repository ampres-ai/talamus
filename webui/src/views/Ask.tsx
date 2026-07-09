import { useState } from "react";
import { api, AskResult, AskSource } from "../api";

const EXAMPLES = [
  "How does reranking work?",
  "What is retrieval-augmented generation?",
  "Why use embeddings?",
];

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 16,
};

function proseOf(answer: string): string {
  const i = answer.lastIndexOf("\n\n**Sources:**");
  return (i >= 0 ? answer.slice(0, i) : answer).trim();
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <span style={{ color: "var(--muted)", fontSize: 12 }}>
      {label} <span style={{ color: "var(--text)" }}>{value}</span>
    </span>
  );
}

function Sources({
  sources,
  heading,
  onOpenNote,
}: {
  sources: AskSource[];
  heading: string;
  onOpenNote?: (t: string) => void;
}) {
  if (sources.length === 0) return null;
  return (
    <div style={{ marginTop: 14 }}>
      <div
        style={{
          color: "var(--accent-2)",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: 0.8,
          textTransform: "uppercase",
          marginBottom: 8,
        }}
      >
        {heading}
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        {sources.map((s, i) => (
          <div
            key={s.title + i}
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "8px 12px",
            }}
          >
            <button
              onClick={() => onOpenNote?.(s.title)}
              style={{
                background: "none",
                border: "none",
                padding: 0,
                color: "var(--accent-2)",
                cursor: "pointer",
                font: "inherit",
                fontWeight: 500,
                textDecoration: "underline",
              }}
            >
              {s.title}
            </button>
            {s.summary ? (
              <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>{s.summary}</div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function Answer({ res, onOpenNote }: { res: AskResult; onOpenNote?: (t: string) => void }) {
  if (res.answered) {
    return (
      <div style={{ ...panel, borderLeft: "3px solid var(--accent)" }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 12, alignItems: "center" }}>
          <Meta label="engine" value={res.engine || "—"} />
          {res.route ? <Meta label="route" value={res.route} /> : null}
          {res.context_tokens ? (
            <Meta label="cost" value={`${res.context_tokens.toLocaleString()} tokens`} />
          ) : null}
          {res.as_of ? (
            <span
              style={{
                background: "var(--accent-soft)",
                border: "1px solid var(--accent-line)",
                color: "var(--accent-1)",
                fontSize: 11,
                fontWeight: 600,
                borderRadius: 999,
                padding: "2px 10px",
              }}
              title="Answered from the brain as it was at this time"
            >
              as of {res.as_of}
            </span>
          ) : null}
        </div>
        <div
          style={{
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontSize: 14.5,
            lineHeight: 1.7,
            color: "var(--text)",
          }}
        >
          {proseOf(res.answer)}
        </div>
        <Sources sources={res.sources} heading="Cited from your brain" onOpenNote={onOpenNote} />
      </div>
    );
  }
  // Degraded: no engine (or unreachable) — retrieval still answers with the notes.
  return (
    <div style={{ ...panel, borderLeft: "3px solid var(--warn)" }}>
      <div style={{ color: "var(--warn)", fontSize: 13, marginBottom: 4, fontWeight: 500 }}>
        Showing relevant notes
      </div>
      <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.55 }}>{res.notice}</div>
      <Sources sources={res.sources} heading="Most relevant notes" onOpenNote={onOpenNote} />
    </div>
  );
}

export function Ask({ onOpenNote }: { onOpenNote?: (title: string) => void }) {
  const [q, setQ] = useState("");
  const [asOf, setAsOf] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (question: string) => {
    const text = question.trim();
    if (!text || loading) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      const r = await api.ask(text, asOf.trim() || undefined);
      if (r.data) setRes(r.data);
      else setError(r.message ?? "Ask a question first.");
    } catch {
      setError("Could not reach the brain.");
    } finally {
      setLoading(false);
    }
  };

  const ask = (question?: string) => {
    const text = question ?? q;
    if (question) setQ(question);
    run(text);
  };

  return (
    <div style={{ maxWidth: 820, margin: "0 auto" }}>
      <h2 style={{ marginTop: 0 }}>Ask your memory</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        Ask in plain language. Every answer is grounded in your notes and cites them — nothing is
        invented.
      </div>

      <div style={{ ...panel, padding: 12 }}>
        <textarea
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask();
            }
          }}
          placeholder="What do you want to know?"
          rows={3}
          style={{
            width: "100%",
            resize: "vertical",
            background: "var(--bg)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "10px 12px",
            font: "inherit",
            fontSize: 14.5,
            lineHeight: 1.6,
          }}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={() => ask()} disabled={loading || !q.trim()}>
            {loading ? "Thinking…" : "Ask"}
          </button>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Enter to ask · Shift+Enter for a new line</span>
          <span style={{ flex: 1 }} />
          <label style={{ color: "var(--muted)", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            as of
            <input
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              placeholder="now"
              title="Answer from the brain as it was at a past date (e.g. 2026-01)"
              style={{
                width: 96,
                background: "var(--bg)",
                color: "var(--text)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "4px 8px",
                font: "inherit",
                fontSize: 12.5,
              }}
            />
          </label>
        </div>
      </div>

      {!res && !loading && !error ? (
        <div style={{ marginTop: 18 }}>
          <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 8 }}>Try asking</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                className="btn"
                onClick={() => ask(ex)}
                style={{ fontSize: 13 }}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {loading ? (
        <div style={{ ...panel, marginTop: 16, color: "var(--muted)" }}>
          Consulting your brain — routing, reading notes, composing a cited answer…
        </div>
      ) : null}

      {error ? (
        <div
          style={{ ...panel, marginTop: 16, borderColor: "var(--danger)", color: "var(--danger)", fontSize: 13 }}
        >
          {error}
        </div>
      ) : null}

      {res && !loading ? (
        <div style={{ marginTop: 16 }}>
          <Answer res={res} onOpenNote={onOpenNote} />
        </div>
      ) : null}
    </div>
  );
}
