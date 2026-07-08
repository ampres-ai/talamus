import { useEffect, useState } from "react";
import { ClockCounterClockwise, Info, SealCheck, SealWarning, X } from "@phosphor-icons/react";
import { api, VerifyResult } from "../api";
import { Markdown } from "../markdown";

// split YAML frontmatter (metadata) from the note body
function splitNote(md: string): { meta: string; body: string } {
  const m = md.match(/^---\n([\s\S]*?)\n---\n?/);
  if (m) return { meta: m[1].trim(), body: md.slice(m[0].length).trim() };
  return { meta: "", body: md.trim() };
}

function versionText(version: Record<string, unknown>): string {
  const summary = String(version["summary"] ?? "");
  const sections = (version["body_sections"] ?? {}) as Record<string, unknown>;
  const body = Object.values(sections)
    .map((v) => String(v))
    .join("\n\n");
  return [summary, body].filter(Boolean).join("\n\n");
}

export function Inspector({ title, onClose }: { title: string; onClose: () => void }) {
  const [md, setMd] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const [showMeta, setShowMeta] = useState(false);
  // TIME moat: read the note as it was at a past date
  const [showAsOf, setShowAsOf] = useState(false);
  const [asOfInput, setAsOfInput] = useState("");
  const [asOfView, setAsOfView] = useState<{ when: string; text: string | null } | null>(null);
  // VERIFIABILITY moat: check the note against its preserved source
  const [verifying, setVerifying] = useState(false);
  const [verdict, setVerdict] = useState<VerifyResult | { error: string } | null>(null);

  useEffect(() => {
    setMd(null);
    setMissing(false);
    setShowMeta(false);
    setShowAsOf(false);
    setAsOfInput("");
    setAsOfView(null);
    setVerifying(false);
    setVerdict(null);
    api
      .note(title)
      .then((r) => {
        if (r.data.found && r.data.markdown) setMd(r.data.markdown);
        else setMissing(true);
      })
      .catch(() => setMissing(true));
  }, [title]);

  const loadAsOf = (when: string) => {
    if (!when.trim()) {
      setAsOfView(null);
      return;
    }
    setAsOfView({ when, text: null });
    api
      .note(title, when)
      .then((r) => {
        if (r.data.version) setAsOfView({ when, text: versionText(r.data.version) });
        else setAsOfView({ when, text: `No version of this note existed at ${when}.` });
      })
      .catch(() => setAsOfView({ when, text: "Could not read the history." }));
  };

  const runVerify = () => {
    setVerifying(true);
    setVerdict(null);
    api
      .verify(title)
      .then((r) => {
        if (!r.success || !r.data) setVerdict({ error: r.message ?? "verification failed" });
        else setVerdict(r.data as VerifyResult);
      })
      .catch((e) => setVerdict({ error: String(e) }))
      .finally(() => setVerifying(false));
  };

  const parsed = md ? splitNote(md) : null;
  const hasMeta = !!parsed?.meta;
  const verdictError = verdict && "error" in verdict ? verdict.error : null;
  const verifyVerdict = verdict && !("error" in verdict) ? verdict : null;

  const panelStyle = {
    margin: "0 0 14px",
    padding: 12,
    fontSize: 12.5,
    lineHeight: 1.55,
    background: "var(--surface-2)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-sm)",
  } as const;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 12px 10px 14px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <span style={{ fontWeight: 600, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {title}
        </span>
        <button
          onClick={runVerify}
          disabled={verifying}
          title="Verify against its source (one LLM call)"
          className="icon-btn"
          style={{ color: verdict ? "var(--accent-1)" : "var(--muted)" }}
        >
          <SealCheck size={17} weight={verdict ? "fill" : "regular"} />
        </button>
        <button
          onClick={() => setShowAsOf((v) => !v)}
          title="Time travel: read the note as it was at a date"
          aria-pressed={showAsOf}
          className="icon-btn"
          style={{ color: showAsOf ? "var(--accent-1)" : "var(--muted)" }}
        >
          <ClockCounterClockwise size={17} weight={showAsOf ? "fill" : "regular"} />
        </button>
        {hasMeta ? (
          <button
            onClick={() => setShowMeta((v) => !v)}
            title={showMeta ? "Hide metadata" : "Details / metadata"}
            aria-pressed={showMeta}
            className="icon-btn"
            style={{ color: showMeta ? "var(--accent-1)" : "var(--muted)" }}
          >
            <Info size={17} weight={showMeta ? "fill" : "regular"} />
          </button>
        ) : null}
        <button onClick={onClose} aria-label="Close" className="icon-btn" style={{ color: "var(--muted)" }}>
          <X size={16} />
        </button>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: 14, minHeight: 0 }}>
        {verifying ? (
          <div style={{ ...panelStyle, color: "var(--muted)" }}>Verifying against the source...</div>
        ) : verdictError ? (
          <div style={{ ...panelStyle, color: "var(--muted)" }}>{verdictError}</div>
        ) : verifyVerdict ? (
          <div style={{ ...panelStyle, color: "var(--text)" }}>
            {!verifyVerdict.found ? (
              "Note not found."
            ) : !verifyVerdict.checked ? (
              <span style={{ color: "var(--muted)" }}>
                <SealWarning size={14} style={{ verticalAlign: "-2px", marginRight: 6 }} />
                Source unavailable - verification skipped (provenance may be stale).
              </span>
            ) : verifyVerdict.ok ? (
              <span style={{ color: "var(--ok, #4caf82)" }}>
                <SealCheck size={14} weight="fill" style={{ verticalAlign: "-2px", marginRight: 6 }} />
                Still faithful to its source.
              </span>
            ) : (
              <span>
                <SealWarning size={14} weight="fill" style={{ verticalAlign: "-2px", marginRight: 6, color: "var(--warn, #e3b341)" }} />
                Mismatch with its source - proposed correction:{" "}
                <em>{verifyVerdict.summary || verifyVerdict.body || "see the review queue"}</em>
              </span>
            )}
          </div>
        ) : null}

        {showAsOf ? (
          <div style={panelStyle}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                value={asOfInput}
                onChange={(e) => setAsOfInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadAsOf(asOfInput)}
                placeholder="as of... (2026-01 or 2026-01-15)"
                style={{
                  flex: 1,
                  padding: "6px 9px",
                  fontSize: 12.5,
                  color: "var(--text)",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--r-sm)",
                }}
              />
              <button className="btn" onClick={() => loadAsOf(asOfInput)}>
                View
              </button>
              {asOfView ? (
                <button className="btn" onClick={() => setAsOfView(null)}>
                  Now
                </button>
              ) : null}
            </div>
            {asOfView ? (
              <div style={{ marginTop: 10, color: "var(--muted)" }}>
                {asOfView.text === null ? "Reading the history..." : `[as of ${asOfView.when}]`}
              </div>
            ) : null}
          </div>
        ) : null}

        {asOfView && asOfView.text !== null ? (
          <Markdown text={asOfView.text} />
        ) : md === null && !missing ? (
          <div style={{ color: "var(--muted)" }}>Loading...</div>
        ) : missing ? (
          <div style={{ color: "var(--muted)" }}>Note not found.</div>
        ) : (
          <>
            {showMeta && hasMeta ? (
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontFamily: "ui-monospace, monospace",
                  fontSize: 12,
                  lineHeight: 1.55,
                  margin: "0 0 14px",
                  padding: 12,
                  color: "var(--muted)",
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--r-sm)",
                }}
              >
                {parsed!.meta}
              </pre>
            ) : null}
            <Markdown text={parsed!.body || "(no content)"} />
          </>
        )}
      </div>
    </div>
  );
}





