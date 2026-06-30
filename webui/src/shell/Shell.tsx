import { useState, ReactNode, ComponentType } from "react";
import {
  House,
  Sparkle,
  Graph as GraphIc,
  Books,
  DownloadSimple,
  TreeStructure,
  CheckCircle,
  Brain,
  Gauge,
  Stack,
  CaretDown,
  X as XIcon,
  type IconProps,
} from "@phosphor-icons/react";
import { ActiveBrain } from "../api";

type Icon = ComponentType<IconProps>;
type Nav = { id: string; label: string; Icon: Icon };

const NAV: Nav[] = [
  { id: "home", label: "Home", Icon: House },
  { id: "ask", label: "Ask", Icon: Sparkle },
  { id: "graph", label: "Graph", Icon: GraphIc },
  { id: "library", label: "Library", Icon: Books },
  { id: "import", label: "Import", Icon: DownloadSimple },
  { id: "ontology", label: "Ontology", Icon: TreeStructure },
  { id: "review", label: "Review", Icon: CheckCircle },
  { id: "brains", label: "Brains", Icon: Brain },
  { id: "system", label: "System", Icon: Gauge },
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

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: inspector ? "232px 1fr 360px" : "232px 1fr",
        gridTemplateRows: "minmax(0, 1fr)",
        height: "100dvh",
        overflow: "hidden",
      }}
    >
      {/* nav sidebar */}
      <aside
        style={{
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
          borderRight: "1px solid var(--border)",
          background: "rgba(13,17,25,0.6)",
        }}
      >
        <div style={{ padding: "16px 16px 12px", fontWeight: 600, fontSize: 18, letterSpacing: "-0.02em" }}>
          Talamus<span style={{ color: "var(--accent)" }}>●</span>
        </div>
        <div style={{ padding: "0 12px 10px" }}>
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
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Stack size={15} color="var(--accent-2)" />
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
              <CaretDown size={12} color="var(--faint)" style={{ marginLeft: "auto" }} />
            </div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 3 }}>
              {activeBrain
                ? activeBrain.initialized
                  ? `${activeBrain.notes} notes`
                  : "not initialized"
                : "no brain"}
            </div>
          </button>
        </div>
        <nav style={{ padding: "6px 12px", display: "grid", gap: 2, overflow: "auto", minHeight: 0 }}>
          {NAV.map((n) => (
            <button
              key={n.id}
              className={"nav-item" + (active === n.id ? " on" : "")}
              onClick={() => open(n.id)}
              aria-current={active === n.id ? "page" : undefined}
            >
              <span className="ic">
                <n.Icon size={18} weight={active === n.id ? "fill" : "regular"} />
              </span>
              {n.label}
            </button>
          ))}
        </nav>
        <div style={{ flex: 1 }} />
      </aside>

      {/* editor area */}
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0, minHeight: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 2,
            padding: "8px 10px 0",
            borderBottom: "1px solid var(--border)",
            overflowX: "auto",
            background: "rgba(10,14,20,0.35)",
            flexShrink: 0,
          }}
        >
          {openTabs.map((id) => {
            const m = meta(id);
            const I = m?.Icon;
            return (
              <div
                key={id}
                className={"tab" + (active === id ? " on" : "")}
                onClick={() => setActive(id)}
              >
                {I ? (
                  <span style={{ display: "inline-flex", color: active === id ? "var(--accent-1)" : "inherit" }}>
                    <I size={15} weight={active === id ? "fill" : "regular"} />
                  </span>
                ) : null}
                <span className="lbl">{m?.label ?? id}</span>
                <span className="x" onClick={(e) => close(id, e)} title="Close" aria-label="Close tab">
                  <XIcon size={12} />
                </span>
              </div>
            );
          })}
        </div>

        <div
          key={active}
          className="view"
          style={{ flex: 1, overflow: "auto", minHeight: 0, padding: 22 }}
        >
          {active && views[active] ? (
            views[active]
          ) : (
            <div style={{ height: "100%", display: "grid", placeItems: "center", color: "var(--faint)" }}>
              <div style={{ textAlign: "center" }}>
                <Sparkle size={30} color="var(--accent)" weight="duotone" />
                <div style={{ marginTop: 10, fontSize: 14 }}>Pick a view from the left.</div>
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
            flexShrink: 0,
          }}
        >
          <span style={{ color: "var(--ok)" }}>● local-first</span>
          {activeBrain ? <span>{activeBrain.name}</span> : null}
          {meta(active) ? <span style={{ color: "var(--faint)" }}>{meta(active)!.label}</span> : null}
          <span style={{ marginLeft: "auto", color: "var(--faint)" }}>token cost visible</span>
        </footer>
      </main>

      {inspector ? (
        <aside
          style={{
            background: "var(--surface)",
            borderLeft: "1px solid var(--border)",
            overflow: "hidden",
            minHeight: 0,
          }}
        >
          {inspector}
        </aside>
      ) : null}
    </div>
  );
}
