import { useState, ReactNode } from "react";

const NAV = [
  { id: "home", label: "Home", icon: "⌂", tip: "Home — readiness & command center" },
  { id: "ask", label: "Ask", icon: "✦", tip: "Ask — question your memory, get a cited answer" },
  { id: "graph", label: "Graph", icon: "✸", tip: "Graph — the living constellation of notes" },
  { id: "library", label: "Library", icon: "▤", tip: "Library — browse every note" },
  { id: "ontology", label: "Ontology", icon: "❖", tip: "Ontology — the schema that emerges from your notes" },
  { id: "review", label: "Review", icon: "✓", tip: "Review — approve or reject proposed changes" },
  { id: "system", label: "System", icon: "⊙", tip: "System — health, providers & diagnostics" },
];

export function Shell({
  views,
  inspector,
}: {
  views: Record<string, ReactNode>;
  inspector?: ReactNode;
}) {
  const [active, setActive] = useState("home");
  const [openTabs, setOpenTabs] = useState<string[]>(["home"]);
  const open = (id: string) => {
    setActive(id);
    setOpenTabs((t) => (t.includes(id) ? t : [...t, id]));
  };
  const label = (id: string) => NAV.find((n) => n.id === id)?.label ?? id;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: inspector ? "56px 220px 1fr 340px" : "56px 220px 1fr",
        height: "100vh",
      }}
    >
      <nav
        style={{
          background: "var(--surface)",
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: 12,
          gap: 6,
        }}
      >
        {NAV.map((n) => (
          <button
            key={n.id}
            onClick={() => open(n.id)}
            aria-label={n.label}
            title={n.tip}
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              fontSize: 18,
              cursor: "pointer",
              background: active === n.id ? "var(--surface-2)" : "transparent",
              color: active === n.id ? "var(--accent)" : "var(--muted)",
              border: "1px solid " + (active === n.id ? "var(--border)" : "transparent"),
            }}
          >
            {n.icon}
          </button>
        ))}
      </nav>
      <aside
        style={{
          background: "var(--surface)",
          borderRight: "1px solid var(--border)",
          padding: 16,
        }}
      >
        <div style={{ fontWeight: 500, fontSize: 18 }}>
          Talamus<span style={{ color: "var(--accent)" }}>●</span>
        </div>
        <div
          style={{
            color: "var(--muted)",
            fontSize: 12,
            marginTop: 12,
            textTransform: "uppercase",
            letterSpacing: 0.5,
          }}
        >
          {label(active)}
        </div>
      </aside>
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            gap: 4,
            padding: "8px 12px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          {openTabs.map((id) => (
            <button
              key={id}
              onClick={() => setActive(id)}
              style={{
                padding: "6px 12px",
                borderRadius: 8,
                cursor: "pointer",
                background: active === id ? "var(--surface-2)" : "transparent",
                color: active === id ? "var(--text)" : "var(--muted)",
                border: "1px solid " + (active === id ? "var(--border)" : "transparent"),
              }}
            >
              {label(id)}
            </button>
          ))}
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 20 }}>{views[active]}</div>
        <footer
          style={{
            borderTop: "1px solid var(--border)",
            padding: "6px 14px",
            color: "var(--muted)",
            fontSize: 12,
            display: "flex",
            gap: 16,
          }}
        >
          <span style={{ color: "var(--ok)" }}>● local-first</span>
          <span>token cost visible</span>
        </footer>
      </main>
      {inspector ? (
        <aside
          style={{
            background: "var(--surface)",
            borderLeft: "1px solid var(--border)",
            overflow: "hidden",
          }}
        >
          {inspector}
        </aside>
      ) : null}
    </div>
  );
}
