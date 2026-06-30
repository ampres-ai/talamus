import { useState, ReactNode } from "react";
import { ActiveBrain } from "../api";

type Nav = { id: string; label: string; icon: string; tip: string; desc: string };

const NAV: Nav[] = [
  { id: "home", label: "Home", icon: "⌂", tip: "Home", desc: "Readiness & command center" },
  { id: "ask", label: "Ask", icon: "✦", tip: "Ask", desc: "Question your memory, get a cited answer" },
  { id: "graph", label: "Graph", icon: "✸", tip: "Graph", desc: "The living constellation of notes" },
  { id: "library", label: "Library", icon: "▤", tip: "Library", desc: "Browse every note" },
  { id: "import", label: "Import", icon: "⊕", tip: "Import", desc: "Bring documents into your brain" },
  { id: "ontology", label: "Ontology", icon: "❖", tip: "Ontology", desc: "The schema that emerges from your notes" },
  { id: "review", label: "Review", icon: "✓", tip: "Review", desc: "Approve or reject proposed changes" },
  { id: "brains", label: "Brains", icon: "⊞", tip: "Brains", desc: "Switch the active brain" },
  { id: "system", label: "System", icon: "⊙", tip: "System", desc: "Health, providers & diagnostics" },
];

const meta = (id: string) => NAV.find((n) => n.id === id);

export function Shell({
  views,
  inspector,
  activeBrain,
}: {
  views: Record<string, ReactNode>;
  inspector?: ReactNode;
  activeBrain?: ActiveBrain | null;
}) {
  const [active, setActive] = useState("home");
  const [openTabs, setOpenTabs] = useState<string[]>(["home"]);

  const open = (id: string) => {
    setActive(id);
    setOpenTabs((t) => (t.includes(id) ? t : [...t, id]));
  };
  const close = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setOpenTabs((t) => {
      const i = t.indexOf(id);
      const next = t.filter((x) => x !== id);
      if (active === id) setActive(next[Math.max(0, i - 1)] ?? "");
      return next;
    });
  };

  const current = meta(active);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: inspector ? "54px 248px 1fr 360px" : "54px 248px 1fr",
        height: "100vh",
        overflow: "hidden",
      }}
    >
      {/* activity bar */}
      <nav
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 6,
          paddingTop: 12,
          borderRight: "1px solid var(--border)",
          background: "rgba(10,14,20,0.5)",
        }}
      >
        {NAV.map((n) => (
          <button
            key={n.id}
            className={"act" + (active === n.id ? " on" : "")}
            onClick={() => open(n.id)}
            aria-label={n.label}
            title={n.tip}
          >
            {n.icon}
          </button>
        ))}
      </nav>

      {/* side panel */}
      <aside
        style={{
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid var(--border)",
          background: "var(--surface)",
          minWidth: 0,
        }}
      >
        <div style={{ padding: "16px 16px 12px" }}>
          <div style={{ fontWeight: 600, fontSize: 18, letterSpacing: "-0.02em" }}>
            Talamus<span style={{ color: "var(--accent)" }}>●</span>
          </div>
        </div>
        <div style={{ padding: "0 12px 12px" }}>
          <button
            onClick={() => open("brains")}
            title="Switch brain"
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "9px 11px",
              borderRadius: "var(--r-sm)",
              cursor: "pointer",
              background: "var(--surface-2)",
              border: "1px solid var(--border-2)",
              color: "var(--text)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ color: "var(--accent-2)", fontSize: 12 }}>⊞</span>
              <span
                style={{
                  fontWeight: 600,
                  fontSize: 13,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {activeBrain ? activeBrain.name : "—"}
              </span>
              <span style={{ marginLeft: "auto", color: "var(--faint)", fontSize: 11 }}>▾</span>
            </div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 3 }}>
              {activeBrain
                ? activeBrain.initialized
                  ? `${activeBrain.notes} notes · switch brain`
                  : "not initialized · switch brain"
                : "switch brain"}
            </div>
          </button>
        </div>
        {current ? (
          <div
            style={{
              padding: "14px 16px",
              borderTop: "1px solid var(--border)",
              flex: 1,
              minHeight: 0,
              overflow: "auto",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span style={{ color: "var(--accent-1)", fontSize: 16 }}>{current.icon}</span>
              <span style={{ fontWeight: 600, fontSize: 15 }}>{current.label}</span>
            </div>
            <div style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 6, lineHeight: 1.5 }}>
              {current.desc}
            </div>
          </div>
        ) : (
          <div style={{ flex: 1 }} />
        )}
      </aside>

      {/* editor area */}
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 2,
            padding: "8px 10px 0",
            borderBottom: "1px solid var(--border)",
            overflowX: "auto",
            background: "rgba(10,14,20,0.35)",
          }}
        >
          {openTabs.map((id) => {
            const m = meta(id);
            return (
              <div
                key={id}
                className={"tab" + (active === id ? " on" : "")}
                onClick={() => setActive(id)}
              >
                <span style={{ color: active === id ? "var(--accent-1)" : "inherit", fontSize: 13 }}>
                  {m?.icon}
                </span>
                <span className="lbl">{m?.label ?? id}</span>
                <span className="x" onClick={(e) => close(id, e)} title="Close" aria-label="Close tab">
                  ✕
                </span>
              </div>
            );
          })}
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 22, minHeight: 0 }}>
          {active && views[active] ? (
            views[active]
          ) : (
            <div
              style={{
                height: "100%",
                display: "grid",
                placeItems: "center",
                color: "var(--faint)",
                textAlign: "center",
              }}
            >
              <div>
                <div style={{ fontSize: 30, color: "var(--accent)", opacity: 0.5 }}>●</div>
                <div style={{ marginTop: 10, fontSize: 14 }}>
                  Talamus — pick a view from the left rail.
                </div>
              </div>
            </div>
          )}
        </div>
        <footer
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            padding: "5px 14px",
            borderTop: "1px solid var(--border)",
            color: "var(--muted)",
            fontSize: 11.5,
            background: "rgba(10,14,20,0.5)",
          }}
        >
          <span style={{ color: "var(--ok)" }}>● local-first</span>
          {activeBrain ? <span>{activeBrain.name}</span> : null}
          {current ? <span style={{ color: "var(--faint)" }}>{current.label}</span> : null}
          <span style={{ marginLeft: "auto", color: "var(--faint)" }}>token cost visible</span>
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
