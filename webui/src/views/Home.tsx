import { useEffect, useState } from "react";
import { api } from "../api";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: 14,
        minWidth: 150,
      }}
    >
      <div style={{ color: "var(--muted)", fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 500, marginTop: 4 }}>{value}</div>
    </div>
  );
}

export function Home() {
  const [d, setD] = useState<Record<string, any> | null>(null);
  useEffect(() => {
    api
      .readiness()
      .then((r) => setD(r.data))
      .catch(() => setD({}));
  }, []);
  if (!d) return <div style={{ color: "var(--muted)" }}>Loading…</div>;
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Command center</h2>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Metric label="Brain" value={`${d.notes ?? 0} notes`} />
        <Metric label="Sources" value={`${d.sources ?? 0}`} />
        <Metric label="Reviews" value={`${d.reviews_pending ?? 0}`} />
        <Metric label="Index" value={String(d.index_backend ?? "—")} />
      </div>
    </div>
  );
}
