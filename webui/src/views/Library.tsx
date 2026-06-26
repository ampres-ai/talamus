import { useEffect, useState } from "react";
import { api, NoteSummary } from "../api";

export function Library() {
  const [notes, setNotes] = useState<NoteSummary[]>([]);
  useEffect(() => {
    api
      .library()
      .then((r) => setNotes(r.data.notes))
      .catch(() => setNotes([]));
  }, []);
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Library</h2>
      {notes.map((n) => (
        <div
          key={n.title}
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: 12,
            marginBottom: 8,
          }}
        >
          <div style={{ fontWeight: 500 }}>{n.title}</div>
          <div style={{ color: "var(--muted)", fontSize: 13 }}>{n.summary}</div>
        </div>
      ))}
    </div>
  );
}
