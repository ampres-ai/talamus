import { useEffect, useState } from "react";
import { api, Diagnostics, DiagnosticCheck } from "../api";

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 16,
};

const STATUS_COLOR: Record<string, string> = {
  ok: "var(--ok)",
  warning: "var(--warn)",
  error: "var(--danger)",
};

function Section({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        color: "var(--accent-2)",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: 0.8,
        textTransform: "uppercase",
        margin: "18px 0 8px",
      }}
    >
      {children}
    </div>
  );
}

function fmtBytes(n: number): string {
  if (!n) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function Tile({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ ...panel, padding: 12, minWidth: 150 }}>
      <div style={{ color: "var(--muted)", fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 500, marginTop: 4, color: tone ?? "var(--text)" }}>
        {value}
      </div>
    </div>
  );
}

function Check({ c }: { c: DiagnosticCheck }) {
  const color = STATUS_COLOR[c.status] ?? "var(--muted)";
  return (
    <div
      style={{
        ...panel,
        padding: 12,
        marginBottom: 8,
        display: "flex",
        gap: 12,
        alignItems: "flex-start",
      }}
    >
      <span
        title={c.status}
        style={{
          width: 9,
          height: 9,
          borderRadius: "50%",
          background: color,
          marginTop: 5,
          flexShrink: 0,
          boxShadow: `0 0 6px ${color}`,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 500 }}>
          {c.label} <span style={{ color: "var(--muted)", fontWeight: 400 }}>· {c.message}</span>
        </div>
        {c.detail ? (
          <div
            style={{
              color: "var(--muted)",
              fontSize: 12,
              marginTop: 2,
              wordBreak: "break-all",
            }}
          >
            {c.detail}
          </div>
        ) : null}
        {c.action ? (
          <div style={{ color: "var(--accent-2)", fontSize: 12.5, marginTop: 4 }}>→ {c.action}</div>
        ) : null}
      </div>
    </div>
  );
}

export function System() {
  const [d, setD] = useState<Diagnostics | null>(null);
  useEffect(() => {
    api
      .diagnostics()
      .then((r) => setD(r.data))
      .catch(() => setD(null));
  }, []);

  if (!d) return <div style={{ color: "var(--muted)" }}>Loading…</div>;

  const tone = d.ok ? "var(--ok)" : "var(--danger)";
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>System</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        Local health, the stack powering your brain, and what to run next.
      </div>

      <div style={{ ...panel, borderLeft: `3px solid ${tone}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: tone, fontSize: 16 }}>●</span>
          <span style={{ fontWeight: 500 }}>
            {d.ok ? "All systems healthy" : "Needs attention"}
          </span>
        </div>
        <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4, wordBreak: "break-all" }}>
          {d.root}
        </div>
      </div>

      <Section>Health checks</Section>
      {d.checks.map((c, i) => (
        <Check key={c.check_id + i} c={c} />
      ))}

      <Section>Stack</Section>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Tile label="Storage" value={d.storage_provider} />
        <Tile label="Search" value={d.search_provider} />
        <Tile label="Index" value={`${d.index_backend} · ${fmtBytes(d.index_bytes)}`} />
        <Tile label="Graph" value={d.graph_provider} />
        <Tile
          label="LLM engine"
          value={`${d.llm_provider} · ${d.llm_status}`}
          tone={d.llm_status === "ok" ? "var(--ok)" : "var(--warn)"}
        />
        <Tile label="PDF" value={d.pdf_converter} />
        <Tile label="OCR" value={d.ocr_provider === "none" ? "none" : `${d.ocr_provider}`} />
      </div>

      <Section>Brain</Section>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Tile label="Notes" value={String(d.notes)} />
        <Tile
          label="Overview"
          value={d.overview_built ? `${d.overview_domains} domains` : "not built"}
          tone={d.overview_built ? "var(--text)" : "var(--warn)"}
        />
        <Tile
          label="Cache"
          value={d.cache_current ? "fresh" : "stale"}
          tone={d.cache_current ? "var(--ok)" : "var(--warn)"}
        />
      </div>
    </div>
  );
}
