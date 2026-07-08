import { useEffect, useState, type ComponentType, type CSSProperties, type FormEvent } from "react";
import {
  ArrowRight,
  CheckCircle,
  DownloadSimple,
  Graph,
  PlugsConnected,
  Sparkle,
  type IconProps,
} from "@phosphor-icons/react";
import { api } from "../api";

type Engine = {
  provider?: string;
  label?: string;
  available?: boolean;
  configured?: boolean;
  status?: string;
};

type Readiness = {
  root?: string;
  selected_engine?: string;
  selected_brain?: string;
  engines?: Engine[];
  notes?: number;
  sources?: number;
  reviews_pending?: number;
  cache_current?: boolean;
  index_backend?: string;
  overview_built?: boolean;
  mcp_installed?: boolean;
};

type Icon = ComponentType<IconProps>;
type Action = {
  icon: Icon;
  title: string;
  detail: string;
  view: string;
};

const panel: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid rgba(46,58,79,0.72)",
  borderRadius: "var(--radius)",
};

function asNumber(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}

function asText(v: unknown, fallback = ""): string {
  return typeof v === "string" && v.trim() ? v : fallback;
}

function fmt(n: number): string {
  return new Intl.NumberFormat().format(n);
}

function brainName(d: Readiness): string {
  const selected = asText(d.selected_brain);
  if (selected) return selected;
  const root = asText(d.root);
  if (!root) return "No brain selected";
  const parts = root.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? root;
}

function selectedEngine(d: Readiness): Engine {
  const engines = Array.isArray(d.engines) ? d.engines : [];
  return (
    engines.find((e) => e.configured) ??
    engines.find((e) => e.provider === d.selected_engine) ?? {
      provider: d.selected_engine,
      label: d.selected_engine,
      available: false,
    }
  );
}

function navigate(view: string, query?: string) {
  window.dispatchEvent(
    new CustomEvent("talamus:navigate", {
      detail: query ? { view, query } : { view },
    }),
  );
}

function deriveActions(d: Readiness): Action[] {
  const notes = asNumber(d.notes);
  const reviews = asNumber(d.reviews_pending);
  const actions: Action[] = [];

  if (reviews > 0) {
    actions.push({
      icon: CheckCircle,
      title: `${fmt(reviews)} ${reviews === 1 ? "proposal awaits" : "proposals await"} review`,
      detail: "Accept or reject changes before they become part of the brain.",
      view: "review",
    });
  }
  if (!d.overview_built && notes > 0) {
    actions.push({
      icon: Graph,
      title: "Build the domain map",
      detail: "Generate the overview so Ask can route through meaning, not folders.",
      view: "ontology",
    });
  }
  if (!d.mcp_installed) {
    actions.push({
      icon: PlugsConnected,
      title: "Connect your agents",
      detail: "Install the local bridge so agents can read from this brain.",
      view: "connect",
    });
  }
  if (notes < 5) {
    actions.push({
      icon: DownloadSimple,
      title: "Feed the brain",
      detail:
        notes === 0
          ? "Import notes or a vault to give Talamus source material."
          : "Add more source material before judging recall.",
      view: "import",
    });
  }

  return actions.slice(0, 4);
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ ...panel, padding: "13px 14px", minWidth: 140, flex: "1 1 140px" }}>
      <div style={{ color: "var(--muted)", fontSize: 11.5 }}>{label}</div>
      <div
        className="tnum"
        style={{ color: tone ?? "var(--text)", fontSize: 16, fontWeight: 600, marginTop: 3 }}
      >
        {value}
      </div>
    </div>
  );
}

function EngineChip({ engine }: { engine: Engine }) {
  const ok = !!engine.available || engine.status === "ready";
  const color = ok ? "var(--ok)" : "var(--warn)";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        color: "var(--text)",
        background: "var(--surface-2)",
        border: "1px solid var(--border-2)",
        borderRadius: 999,
        padding: "6px 10px",
        fontSize: 12.5,
        fontWeight: 500,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 8px ${color}`,
        }}
      />
      {asText(engine.label, asText(engine.provider, "engine"))}
    </span>
  );
}

function ActionCard({ action }: { action: Action }) {
  const [hover, setHover] = useState(false);
  const I = action.icon;
  return (
    <button
      onClick={() => navigate(action.view)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        ...panel,
        width: "100%",
        minHeight: 116,
        padding: 16,
        color: "var(--text)",
        textAlign: "left",
        cursor: "pointer",
        boxShadow: hover ? "var(--shadow)" : "0 1px 0 rgba(255,255,255,0.02)",
        transform: hover ? "translateY(-2px)" : "translateY(0)",
        transition:
          "transform 0.18s var(--ease), box-shadow 0.18s var(--ease), border-color 0.18s var(--ease)",
        borderColor: hover ? "var(--accent-line)" : "rgba(46,58,79,0.72)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 13 }}>
        <span
          style={{
            display: "grid",
            placeItems: "center",
            width: 34,
            height: 34,
            borderRadius: 9,
            color: "var(--accent-2)",
            background: "rgba(79,195,247,0.1)",
            flexShrink: 0,
          }}
        >
          <I size={18} weight="duotone" />
        </span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ display: "block", fontSize: 15, fontWeight: 600 }}>{action.title}</span>
          <span
            style={{
              display: "block",
              color: "var(--muted)",
              fontSize: 12.5,
              lineHeight: 1.5,
              marginTop: 4,
            }}
          >
            {action.detail}
          </span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              color: "var(--accent-2)",
              fontSize: 12.5,
              marginTop: 10,
            }}
          >
            Open {action.view} <ArrowRight size={13} />
          </span>
        </span>
      </div>
    </button>
  );
}

export function Home() {
  const [d, setD] = useState<Readiness | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    api
      .readiness()
      .then((r) => setD((r.data ?? {}) as Readiness))
      .catch(() => setD({}));
  }, []);

  if (!d) return <div style={{ color: "var(--muted)" }}>Loading...</div>;

  const notes = asNumber(d.notes);
  const sources = asNumber(d.sources);
  const reviews = asNumber(d.reviews_pending);
  const engine = selectedEngine(d);
  const engineOk = !!engine.available || engine.status === "ready";
  const actions = deriveActions(d);

  const ask = (e: FormEvent) => {
    e.preventDefault();
    navigate("ask", q.trim() || undefined);
  };

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto" }}>
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) auto",
          gap: 24,
          alignItems: "end",
          marginBottom: 24,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
            <EngineChip engine={engine} />
            <span style={{ color: engineOk ? "var(--ok)" : "var(--warn)", fontSize: 12.5 }}>
              {engineOk ? "Engine ready" : "Engine needs attention"}
            </span>
          </div>
          <h1
            style={{
              fontSize: 54,
              lineHeight: 0.95,
              letterSpacing: "-0.04em",
              margin: 0,
              overflowWrap: "anywhere",
            }}
          >
            {brainName(d)}
          </h1>
          <div style={{ color: "var(--muted)", fontSize: 15, marginTop: 12 }}>
            {fmt(notes)} notes - {fmt(sources)} sources
          </div>
        </div>
        <div style={{ textAlign: "right", minWidth: 170 }}>
          <div
            className="tnum"
            style={{ color: "var(--text)", fontSize: 72, lineHeight: 0.9, fontWeight: 650, letterSpacing: "-0.04em" }}
          >
            {fmt(notes)}
          </div>
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>notes indexed</div>
        </div>
      </section>

      <section style={{ marginBottom: 24 }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Next actions
        </div>
        {actions.length ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 12 }}>
            {actions.map((action) => (
              <ActionCard key={action.title} action={action} />
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--muted)", fontSize: 14 }}>All quiet. The brain is current.</div>
        )}
      </section>

      <section style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
        <Stat label="Notes" value={fmt(notes)} />
        <Stat label="Sources" value={fmt(sources)} />
        <Stat label="Pending reviews" value={fmt(reviews)} tone={reviews ? "var(--warn)" : "var(--text)"} />
        <Stat label="Index backend" value={asText(d.index_backend, "none")} />
        <Stat label="Cache" value={d.cache_current ? "ok" : "stale"} tone={d.cache_current ? "var(--ok)" : "var(--warn)"} />
      </section>

      <section style={{ ...panel, padding: 16, borderLeft: "3px solid var(--accent)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 11 }}>
          <Sparkle size={18} color="var(--accent-2)" weight="duotone" />
          <div style={{ fontWeight: 600 }}>Quick ask</div>
        </div>
        <form onSubmit={ask} style={{ display: "flex", gap: 10 }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask this brain..."
            style={{
              flex: 1,
              minWidth: 0,
              background: "var(--bg)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "10px 12px",
              font: "inherit",
              fontSize: 14,
            }}
          />
          <button className="btn btn-primary" type="submit">
            Ask
          </button>
        </form>
      </section>
    </div>
  );
}