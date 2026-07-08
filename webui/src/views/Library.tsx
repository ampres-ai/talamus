import { useEffect, useState } from "react";
import { api, NoteSummary } from "../api";
import { Markdown } from "../markdown";

function splitNote(md: string): { meta: string; body: string } {
  const m = md.match(/^---\n([\s\S]*?)\n---\n?/);
  if (m) return { meta: m[1].trim(), body: md.slice(m[0].length).trim() };
  return { meta: "", body: md.trim() };
}

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 16,
};

export function Library({ onOpenNote }: { onOpenNote?: (title: string) => void }) {
  const [notes, setNotes] = useState<NoteSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    api
      .library()
      .then((r) => {
        const loaded = r.data.notes;
        setNotes(loaded);
        if (!selected && loaded.length > 0) setSelected(loaded[0].title);
      })
      .catch(() => setNotes([]));
  }, [selected]);

  useEffect(() => {
    if (!selected) {
      setMarkdown(null);
      setDetailError("");
      return;
    }
    setMarkdown(null);
    setDetailError("");
    api
      .note(selected)
      .then((r) => {
        if (r.data.found && r.data.markdown) setMarkdown(r.data.markdown);
        else setDetailError("Note not found.");
      })
      .catch(() => setDetailError("Could not read this note."));
  }, [selected]);

  const parsed = markdown ? splitNote(markdown) : null;

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
        Every note in this brain. Select one to read its rendered Markdown.
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
          No notes yet. Head to Import to bring documents into this brain.
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 0.9fr) minmax(280px, 1.4fr)", gap: 12 }}>
          <div className="stagger" style={{ display: "grid", gap: 8, alignContent: "start" }}>
            {notes.map((n, i) => (
              <button
                key={n.title}
                onClick={() => setSelected(n.title)}
                className="note-row"
                aria-pressed={selected === n.title}
                style={{
                  "--i": i,
                  borderColor: selected === n.title ? "var(--accent)" : "var(--border)",
                  background: selected === n.title ? "var(--surface-2)" : "var(--surface)",
                } as React.CSSProperties}
              >
                <div style={{ fontWeight: 600 }}>{n.title}</div>
                <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 3, lineHeight: 1.5 }}>
                  {n.summary}
                </div>
              </button>
            ))}
          </div>

          <article style={{ ...panel, minHeight: 240, alignSelf: "start" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {selected ?? "Select a note"}
                </div>
                {parsed?.meta ? <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 2 }}>Metadata hidden</div> : null}
              </div>
              {selected && onOpenNote ? (
                <button className="btn" onClick={() => onOpenNote(selected)} style={{ fontSize: 12 }}>
                  Inspector
                </button>
              ) : null}
            </div>

            {detailError ? (
              <div style={{ color: "var(--muted)", fontSize: 13 }}>{detailError}</div>
            ) : selected && !parsed ? (
              <div style={{ color: "var(--muted)", fontSize: 13 }}>Loading note...</div>
            ) : parsed ? (
              <Markdown text={parsed.body || "(no content)"} />
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 13 }}>Select a note to read it.</div>
            )}
          </article>
        </div>
      )}
    </div>
  );
}
