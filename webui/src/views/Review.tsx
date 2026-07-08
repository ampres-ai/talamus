import { useCallback, useEffect, useState } from "react";
import { api, ReviewItem } from "../api";
import { Markdown } from "../markdown";

const KIND_HELP: Record<string, string> = {
  correction: "The note appears to disagree with its preserved source.",
  stale_source: "The saved source changed or could not be checked cleanly.",
  low_confidence_note: "An agent proposed this note, but it needs a human decision first.",
  ontology_candidate: "A relation type emerged from the brain and needs promotion or rejection.",
  property: "A relation property was inferred from repeated evidence and needs review.",
  duplicate_concept: "Two concepts may be the same and need a merge decision.",
  scan_safety: "An import or scan looked risky and needs confirmation.",
};

const WORDS: Record<string, string> = {
  correction: "correction",
  stale_source: "stale source warning",
  low_confidence_note: "proposed note",
  ontology_candidate: "ontology candidate",
  property: "ontology property",
  duplicate_concept: "duplicate concept decision",
  scan_safety: "scan safety decision",
};

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 16,
};

function kindLabel(kind: string): string {
  return WORDS[kind] ?? kind.replace(/[_-]/g, " ");
}

function fmtDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString();
}

function textField(detail: Record<string, unknown>, names: string[]): string {
  for (const name of names) {
    const value = detail[name];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function noteTitle(item: ReviewItem): string {
  const fromDetail = textField(item.detail, ["title", "note", "note_title"]);
  if (fromDetail) return fromDetail;
  return item.title.split(":")[0]?.trim() || item.title;
}

function titleLine(item: ReviewItem): string {
  if (item.kind === "correction") return `Proposed correction to ${noteTitle(item)}`;
  return `Proposed ${kindLabel(item.kind)}`;
}

function whyLine(item: ReviewItem): string {
  const detailWhy = textField(item.detail, ["reason", "source", "detail", "status", "message"]);
  if (detailWhy) return detailWhy;
  return KIND_HELP[item.kind] ?? "This item needs a human decision before Talamus changes the brain.";
}

function detailValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((v) => String(v)).join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function proposedMarkdown(item: ReviewItem): string {
  const detail = item.detail;
  const summary = textField(detail, ["summary"]);
  const body = textField(detail, ["body", "text", "content", "proposal", "definition"]);
  if (summary || body) {
    return [summary ? `### Summary\n${summary}` : "", body ? `### Proposed content\n${body}` : ""]
      .filter(Boolean)
      .join("\n\n");
  }
  const entries = Object.entries(detail).filter(
    ([, value]) => value !== "" && value != null && !(Array.isArray(value) && value.length === 0),
  );
  if (entries.length === 0) return "No proposed content was recorded for this item.";
  return entries.map(([key, value]) => `- **${key.replace(/[_-]/g, " ")}**: ${detailValue(value)}`).join("\n");
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: 12,
        color: "var(--warn)",
        background: "rgba(255,183,77,0.13)",
        border: "1px solid rgba(255,183,77,0.35)",
        borderRadius: 999,
        padding: "2px 10px",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

function Guardrail() {
  return (
    <div style={{ ...panel, borderLeft: "3px solid var(--accent)", marginBottom: 16 }}>
      <div style={{ color: "var(--accent-2)", fontSize: 11, fontWeight: 600, letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 6 }}>
        Review guardrail
      </div>
      <div style={{ fontWeight: 500, marginBottom: 4 }}>Proposed changes are never auto-applied.</div>
      <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.55 }}>
        Approve writes the reviewed change when that item type supports it. Reject records your decision and keeps the trail explicit.
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ ...panel, textAlign: "center", padding: "40px 24px" }}>
      <div style={{ fontWeight: 500, marginBottom: 6 }}>Queue is empty. No decisions pending.</div>
      <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.6, maxWidth: 460, margin: "0 auto" }}>
        This is where Talamus pauses before changing the brain. Corrections, uncertain notes, stale sources, and ontology proposals wait here for you.
      </div>
    </div>
  );
}

function ReviewCard({
  item,
  busy,
  onApprove,
  onReject,
  onOpenNote,
}: {
  item: ReviewItem;
  busy: boolean;
  onApprove: () => void;
  onReject: (reason: string) => void;
  onOpenNote?: (title: string) => void;
}) {
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const note = noteTitle(item);

  const reject = () => {
    if (!rejectOpen) {
      setRejectOpen(true);
      return;
    }
    onReject(reason);
  };

  return (
    <article style={{ ...panel, borderLeft: "2px solid var(--warn)", marginBottom: 10 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, lineHeight: 1.35 }}>{titleLine(item)}</div>
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 3 }}>
            {kindLabel(item.kind)} - {item.item_id}
          </div>
        </div>
        <Badge>{item.status}</Badge>
      </div>

      <div style={{ color: "var(--text)", fontSize: 13, lineHeight: 1.55, margin: "12px 0" }}>
        <span style={{ color: "var(--muted)" }}>Why: </span>
        {whyLine(item)}
      </div>

      <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--r-sm)", padding: 12 }}>
        <Markdown text={proposedMarkdown(item)} />
      </div>

      <footer style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
        <div style={{ color: "var(--muted)", fontSize: 12, marginRight: "auto" }}>
          {item.created_at ? `Created ${fmtDate(item.created_at)}` : null}
          {onOpenNote && item.kind === "correction" ? (
            <button
              onClick={() => onOpenNote(note)}
              style={{
                marginLeft: item.created_at ? 10 : 0,
                background: "none",
                border: "none",
                padding: 0,
                color: "var(--accent-2)",
                cursor: "pointer",
                font: "inherit",
                fontSize: 12,
                textDecoration: "underline",
              }}
            >
              Open note
            </button>
          ) : null}
        </div>
        {rejectOpen ? (
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onReject(reason)}
            placeholder="Optional rejection reason"
            style={{
              width: 220,
              maxWidth: "100%",
              padding: "7px 9px",
              fontSize: 12.5,
              color: "var(--text)",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--r-sm)",
            }}
          />
        ) : null}
        <button className="btn btn-primary" onClick={onApprove} disabled={busy}>
          Approve
        </button>
        <button className="btn btn-ghost" onClick={reject} disabled={busy}>
          Reject
        </button>
      </footer>
    </article>
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
        {items !== null ? <span style={{ color: "var(--muted)", fontSize: 14 }}>{pending.length} pending</span> : null}
      </div>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        Human-readable decisions before Talamus changes the brain.
      </div>

      <Guardrail />

      {error ? (
        <div style={{ ...panel, borderColor: "var(--danger)", color: "var(--danger)", fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      ) : null}

      {items === null ? (
        <div style={{ color: "var(--muted)" }}>Loading...</div>
      ) : pending.length === 0 ? (
        <EmptyState />
      ) : (
        pending.map((item) => (
          <ReviewCard
            key={item.item_id}
            item={item}
            busy={busy === item.item_id}
            onApprove={() => act(item.item_id, () => api.applyReview(item.item_id))}
            onReject={(reason) => act(item.item_id, () => api.rejectReview(item.item_id, reason))}
            onOpenNote={onOpenNote}
          />
        ))
      )}
    </div>
  );
}

