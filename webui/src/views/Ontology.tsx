import { useCallback, useEffect, useState } from "react";
import { api, OntologyStatus, OntologyType } from "../api";

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
        marginBottom: 6,
      }}
    >
      {children}
    </div>
  );
}

function Pill({ text, tone }: { text: string; tone: "ready" | "warn" }) {
  const ready = tone === "ready";
  return (
    <span
      style={{
        fontSize: 12,
        color: ready ? "var(--ok)" : "var(--warn)",
        background: ready ? "rgba(130,211,123,0.12)" : "rgba(255,183,77,0.13)",
        border: `1px solid ${ready ? "rgba(130,211,123,0.35)" : "rgba(255,183,77,0.35)"}`,
        borderRadius: 999,
        padding: "2px 10px",
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}

function coverageLine(c: OntologyStatus["coverage"]): string {
  const edges = c.edges ?? 0;
  if (!edges) return "no edges yet";
  const share = Math.round((c.non_related_share ?? 0) * 100);
  return `${c.non_related ?? 0}/${edges} typed edges (${share}%)`;
}

function Insights({ status }: { status: OntologyStatus }) {
  return (
    <div style={{ ...panel, borderLeft: "3px solid var(--accent)", marginBottom: 16 }}>
      <Section>Ontology insights</Section>
      <div style={{ fontWeight: 500, marginBottom: 6 }}>
        Schema {status.schema_id} <span style={{ color: "var(--muted)" }}>v{status.version}</span>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Pill text="Typed coverage" tone="ready" />
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{coverageLine(status.coverage)}</span>
      </div>
      <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.55, marginTop: 10 }}>
        Promotion is a schema decision: candidates stay reviewable until you promote or reject them.
        The graph only draws a relation type once it is active.
      </div>
    </div>
  );
}

function TypeCard({
  t,
  busy,
  onPromote,
  onReject,
}: {
  t: OntologyType;
  busy: boolean;
  onPromote?: () => void;
  onReject?: () => void;
}) {
  const isCandidate = t.status === "candidate";
  return (
    <div
      style={{
        ...panel,
        borderLeft: `2px solid ${isCandidate ? "var(--warn)" : "var(--ok)"}`,
        marginBottom: 10,
      }}
    >
      <div style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontWeight: 500 }}>
            {t.name}
            {t.inverse ? (
              <span style={{ color: "var(--muted)", fontWeight: 400 }}> ⇄ {t.inverse}</span>
            ) : null}
          </div>
          <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
            {t.definition || "(no definition)"}
          </div>
        </div>
        <Pill text={`support ${t.support}`} tone={isCandidate ? "warn" : "ready"} />
      </div>
      <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
        {t.distinct_notes} notes · confidence {Math.round(t.confidence * 100)}%
      </div>
      {t.examples.length ? (
        <div style={{ marginTop: 10 }}>
          <Section>{isCandidate ? "Candidate evidence" : "Evidence"}</Section>
          <div style={{ display: "grid", gap: 3 }}>
            {t.examples.slice(0, 2).map((ex, i) => (
              <div key={i} style={{ color: "var(--text)", fontSize: 13 }}>
                <span style={{ color: "var(--muted)" }}>e.g. </span>
                {ex}
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {isCandidate ? (
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button className="btn btn-primary" onClick={onPromote} disabled={busy}>
            Promote
          </button>
          <button className="btn btn-ghost" onClick={onReject} disabled={busy}>
            Reject
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function Ontology() {
  const [status, setStatus] = useState<OntologyStatus | null>(null);
  const [candidates, setCandidates] = useState<OntologyType[] | null>(null);
  const [active, setActive] = useState<OntologyType[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .ontologyStatus()
      .then((r) => setStatus(r.data))
      .catch(() => setStatus(null));
    api
      .ontologyTypes("candidate")
      .then((r) => setCandidates(r.data ?? []))
      .catch(() => setCandidates([]));
    api
      .ontologyTypes("active")
      .then((r) => setActive(r.data ?? []))
      .catch(() => setActive([]));
  }, []);

  useEffect(() => load(), [load]);

  const act = async (id: string, run: () => Promise<{ success: boolean; message?: string }>) => {
    setBusy(id);
    setError(null);
    try {
      const r = await run();
      if (!r.success) setError(r.message ?? "The schema decision could not be applied.");
      load();
    } catch {
      setError("Could not reach the brain.");
    } finally {
      setBusy(null);
    }
  };

  const pending = candidates ?? [];
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Ontology Lab</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        The schema that emerges from your notes — relation types you decide to promote or reject.
      </div>

      {status ? <Insights status={status} /> : null}

      {error ? (
        <div
          style={{ ...panel, borderColor: "var(--danger)", color: "var(--danger)", fontSize: 13, marginBottom: 12 }}
        >
          {error}
        </div>
      ) : null}

      <Section>Candidates {candidates !== null ? `(${pending.length})` : ""}</Section>
      {candidates === null ? (
        <div style={{ color: "var(--muted)" }}>Loading…</div>
      ) : pending.length === 0 ? (
        <div style={{ ...panel, color: "var(--muted)", fontSize: 13, marginBottom: 16 }}>
          No candidates right now. New relation types surface as your brain grows and the same
          phrasing recurs across notes — they wait here for your decision before joining the schema.
        </div>
      ) : (
        <div style={{ marginBottom: 16 }}>
          {pending.map((t) => (
            <TypeCard
              key={t.id}
              t={t}
              busy={busy === t.id}
              onPromote={() => act(t.id, () => api.promoteOntology(t.id))}
              onReject={() => act(t.id, () => api.rejectOntology(t.id))}
            />
          ))}
        </div>
      )}

      {active.length ? (
        <>
          <Section>Active ({active.length})</Section>
          {active.map((t) => (
            <TypeCard key={t.id} t={t} busy={false} />
          ))}
        </>
      ) : null}
    </div>
  );
}
