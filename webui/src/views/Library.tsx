import { useEffect, useState } from "react";
import { api, NoteSummary } from "../api";

export function Library({ onOpenNote }: { onOpenNote?: (title: string) => void }) {
  const [notes, setNotes] = useState<NoteSummary[] | null>(null);

  useEffect(() => {
    api
      .library()
      .then((r) => setNotes(r.data.notes))
      .catch(() => setNotes([]));
  }, []);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h2 style={{ margin: 0 }}>Library</h2>
        {notes ? (
          <span className="tnum" style={{ color: "var(--muted)", fontSize: 13 }}>
            {notes.length} notes
          </span>
        ) : null}
      </div>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        Every note in this brain — click one to open it.
      </div>

      {notes === null ? (
        <div style={{ display: "grid", gap: 8 }}>
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              style={{
                height: 58,
                borderRadius: "var(--r)",
                background: "var(--surface)",
                border: "1px solid var(--border)",
                opacity: 0.5,
              }}
            />
          ))}
        </div>
      ) : notes.length === 0 ? (
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r)",
            padding: 24,
            color: "var(--muted)",
            fontSize: 13,
            textAlign: "center",
          }}
        >
          No notes yet — head to Import to bring documents into this brain.
        </div>
      ) : (
        <div className="stagger" style={{ display: "grid", gap: 8 }}>
          {notes.map((n, i) => (
            <button
              key={n.title}
              onClick={() => onOpenNote?.(n.title)}
              className="note-row"
              style={{ "--i": i } as React.CSSProperties}
            >
              <div style={{ fontWeight: 600 }}>{n.title}</div>
              <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 3, lineHeight: 1.5 }}>
                {n.summary}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
