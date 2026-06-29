import { useEffect, useState } from "react";
import { api, BrainItem, BrainList } from "../api";

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 16,
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

function Badge({ text, color, bg, border }: { text: string; color: string; bg: string; border: string }) {
  return (
    <span
      style={{
        fontSize: 11,
        color,
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: 999,
        padding: "2px 9px",
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}

function BrainCard({ b }: { b: BrainItem }) {
  return (
    <div
      style={{
        ...panel,
        borderLeft: `2px solid ${b.selected ? "var(--accent)" : "var(--border)"}`,
        marginBottom: 10,
      }}
    >
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontWeight: 500 }}>{b.name}</span>
        {b.selected ? (
          <Badge text="active" color="var(--accent-2)" bg="rgba(110,91,255,0.16)" border="rgba(110,91,255,0.45)" />
        ) : null}
        <Badge text={b.type} color="var(--muted)" bg="var(--surface-2)" border="var(--border)" />
        {b.federated ? (
          <Badge text="federated" color="var(--accent-2)" bg="rgba(79,195,247,0.12)" border="rgba(79,195,247,0.35)" />
        ) : null}
        {b.sensitive ? (
          <Badge text="sensitive" color="var(--warn)" bg="rgba(255,183,77,0.13)" border="rgba(255,183,77,0.35)" />
        ) : null}
        {!b.exists ? (
          <Badge text="missing" color="var(--danger)" bg="rgba(255,138,138,0.12)" border="rgba(255,138,138,0.4)" />
        ) : null}
        <span style={{ flex: 1 }} />
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{b.notes} notes</span>
      </div>
      <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6, wordBreak: "break-all" }}>
        {b.path}
      </div>
    </div>
  );
}

export function Brains() {
  const [d, setD] = useState<BrainList | null>(null);
  useEffect(() => {
    api
      .brains()
      .then((r) => setD(r.data))
      .catch(() => setD(null));
  }, []);

  if (!d) return <div style={{ color: "var(--muted)" }}>Loading…</div>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Brains</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        Every local brain Talamus knows — federation and scope at a glance.
      </div>

      <div style={{ ...panel, borderLeft: "3px solid var(--accent)" }}>
        <div
          style={{
            color: "var(--accent-2)",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: 0.8,
            textTransform: "uppercase",
            marginBottom: 6,
          }}
        >
          Scope guardrails
        </div>
        <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.55 }}>
          Federated brains can answer shared queries; sensitive brains stay out of broad retrieval.
          The active brain is the one a web session is launched against.
        </div>
        <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8, wordBreak: "break-all" }}>
          Registry: {d.registry_path}
        </div>
      </div>

      <Section>Registered {d.brains.length ? `(${d.brains.length})` : ""}</Section>
      {d.brains.length === 0 ? (
        <div style={{ ...panel, color: "var(--muted)", fontSize: 13 }}>
          No brains registered yet. <code>talamus init</code> registers one; each is a local
          folder of Markdown notes.
        </div>
      ) : (
        d.brains.map((b) => <BrainCard key={b.id} b={b} />)
      )}

      {d.unregistered.length ? (
        <>
          <Section>Unregistered ({d.unregistered.length})</Section>
          {d.unregistered.map((u) => (
            <div key={u.path} style={{ ...panel, marginBottom: 10 }}>
              <div style={{ fontWeight: 500 }}>{u.name}</div>
              <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4, wordBreak: "break-all" }}>
                {u.path}
              </div>
              <code
                style={{
                  display: "inline-block",
                  marginTop: 8,
                  fontSize: 12,
                  color: "var(--accent-2)",
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  padding: "3px 8px",
                }}
              >
                {u.register_command}
              </code>
            </div>
          ))}
        </>
      ) : null}
    </div>
  );
}
