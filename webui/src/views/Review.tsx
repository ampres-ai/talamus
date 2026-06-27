import { useCallback, useEffect, useState } from "react";
import { api, ReviewItem } from "../api";

const LANES: Record<string, string> = {
  correction: "Source fidelity",
  stale_source: "Source freshness",
  low_confidence_note: "Confidence",
  ontology_candidate: "Ontology",
  duplicate_concept: "Ontology",
  scan_safety: "Manual decision",
};

const KIND_HELP: Record<string, string> = {
  correction: "A note disagrees with its source — apply to write the reviewed fix.",
  stale_source: "A source changed since it was read — apply to refresh it.",
  low_confidence_note: "An agent proposed an uncertain note — it never lands unreviewed.",
  ontology_candidate: "A new relation type emerged — promote it into the schema.",
  duplicate_concept: "Two concepts may be the same — decide whether to merge.",
  scan_safety: "An import looked risky — confirm before it enters the brain.",
};

const kindLabel = (kind: string) => kind.replace(/[_-]/g, " ");
const lane = (kind: string) => LANES[kind] ?? "Manual decision";

function fmtDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString();
}

function Section({ children }: { children: React.ReactNode }) {
  return (
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
      {children}
    </div>
  );
}

function Pill({ text, tone = "warn" }: { text: string; tone?: "warn" | "accent" }) {
  const c = tone === "accent" ? "var(--accent-2)" : "var(--warn)";
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: 12,
        color: c,
        background: tone === "accent" ? "rgba(79,195,247,0.12)" : "rgba(255,183,77,0.13)",
        border: `1px solid ${tone === "accent" ? "rgba(79,195,247,0.35)" : "rgba(255,183,77,0.35)"}`,
        borderRadius: 999,
        padding: "2px 10px",
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}

function Evidence({ detail, onOpenNote }: { detail: Record<string, unknown>; onOpenNote?: (t: string) => void }) {
  const entries = Object.entries(detail).filter(
    ([, v]) => v !== "" && v != null && !(Array.isArray(v) && v.length === 0),
  );
  if (entries.length === 0)
    return <div style={{ color: "var(--muted)", fontSize: 13 }}>No evidence detail recorded.</div>;
  return (
    <div style={{ display: "grid", gap: 4 }}>
      {entries.map(([k, v]) => {
        const note = (k === "title" || k === "note") && typeof v === "string" ? v : null;
        return (
          <div key={k} style={{ fontSize: 13, color: "var(--text)" }}>
            <span style={{ color: "var(--muted)" }}>{k}: </span>
            {note && onOpenNote ? (
              <button
                onClick={() => onOpenNote(note)}
                style={{
                  background: "none",
                  border: "none",
                  padding: 0,
                  color: "var(--accent-2)",
                  cursor: "pointer",
                  font: "inherit",
                  fontSize: 13,
                  textDecoration: "underline",
                }}
              >
                {note}
              </button>
            ) : (
              <span>{String(v)}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 16,
};

function Guardrail() {
  return (
    <div style={{ ...panel, borderLeft: "3px solid var(--accent)", marginBottom: 16 }}>
      <Section>Review guardrail</Section>
      <div style={{ fontWeight: 500, marginBottom: 4 }}>Proposed changes are never auto-applied.</div>
      <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.55 }}>
        Apply writes the reviewed change to the brain; Reject records your decision. Rejections stay
        logged — Talamus keeps every correction explicit and traceable.
      </div>
    </div>
  );
}

function DecisionQueue({ items }: { items: ReviewItem[] }) {
  const counts = new Map<string, number>();
  const lanes: string[] = [];
  for (const it of items) {
    const label = kindLabel(it.kind);
    counts.set(label, (counts.get(label) ?? 0) + 1);
    const l = lane(it.kind);
    if (!lanes.includes(l)) lanes.push(l);
  }
  return (
    <div style={{ ...panel, marginBottom: 16 }}>
      <Section>Decision queue</Section>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {[...counts.entries()]
          .sort((a, b) => a[0].localeCompare(b[0]))
          .map(([label, n]) => (
            <Pill key={label} text={`${n} ${label}`} />
          ))}
      </div>
      <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 10 }}>{lanes.join(" · ")}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ ...panel, textAlign: "center", padding: "40px 24px" }}>
      <div style={{ fontSize: 28, marginBottom: 8 }}>✓</div>
      <div style={{ fontWeight: 500, marginBottom: 6 }}>Queue is empty — no decisions pending.</div>
      <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.6, maxWidth: 460, margin: "0 auto" }}>
        This is where Talamus pauses for you. Items land here when a note disagrees with its source,
        a source goes stale, an agent proposes an uncertain note, or a new ontology relation emerges —
        nothing changes the brain until you approve it.
      </div>
    </div>
  );
}

function Card({
  item,
  busy,
  onApply,
  onReject,
  onOpenNote,
}: {
  item: ReviewItem;
  busy: boolean;
  onApply: () => void;
  onReject: () => void;
  onOpenNote?: (t: string) => void;
}) {
  return (
    <div style={{ ...panel, borderLeft: "2px solid var(--warn)", marginBottom: 10 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontWeight: 500 }}>{item.title}</div>
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 2 }}>
            {kindLabel(item.kind)} · {item.item_id}
          </div>
        </div>
        <Pill text={item.status} />
      </div>
      <div style={{ color: "var(--muted)", fontSize: 12.5, margin: "8px 0 10px" }}>
        {KIND_HELP[item.kind] ?? "Review this proposed change before it enters the brain."}
      </div>
      <div style={{ marginBottom: 10 }}>
        <Section>Evidence</Section>
        <Evidence detail={item.detail} onOpenNote={onOpenNote} />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button className="btn btn-primary" onClick={onApply} disabled={busy}>
          Apply
        </button>
        <button className="btn btn-ghost" onClick={onReject} disabled={busy}>
          Reject
        </button>
        <span style={{ flex: 1 }} />
        {item.created_at ? (
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Created {fmtDate(item.created_at)}</span>
        ) : null}
      </div>
    </div>
  );
}

export function Review({ onOpenNote }: { onOpenNote?: (title: string) => void }) {
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .review("pending")
      .then((r) => setItems(r.data ?? []))
      .catch(() => setItems([]));
  }, []);

  useEffect(() => load(), [load]);

  const act = async (id: string, run: () => Promise<{ success: boolean; message?: string }>) => {
    setBusy(id);
    setError(null);
    try {
      const r = await run();
      if (!r.success) setError(r.message ?? "The decision could not be recorded.");
      load();
    } catch {
      setError("Could not reach the brain.");
    } finally {
      setBusy(null);
    }
  };

  const pending = items ?? [];
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <h2 style={{ margin: 0 }}>Review</h2>
        {items !== null ? (
          <span style={{ color: "var(--muted)", fontSize: 14 }}>
            {pending.length} pending
          </span>
        ) : null}
      </div>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        The human checkpoint — where uncertain changes wait for your decision.
      </div>

      <Guardrail />

      {error ? (
        <div
          style={{
            ...panel,
            borderColor: "var(--danger)",
            color: "var(--danger)",
            fontSize: 13,
            marginBottom: 12,
          }}
        >
          {error}
        </div>
      ) : null}

      {items === null ? (
        <div style={{ color: "var(--muted)" }}>Loading…</div>
      ) : pending.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <DecisionQueue items={pending} />
          {pending.map((item) => (
            <Card
              key={item.item_id}
              item={item}
              busy={busy === item.item_id}
              onApply={() => act(item.item_id, () => api.applyReview(item.item_id))}
              onReject={() => act(item.item_id, () => api.rejectReview(item.item_id))}
              onOpenNote={onOpenNote}
            />
          ))}
        </>
      )}
    </div>
  );
}
