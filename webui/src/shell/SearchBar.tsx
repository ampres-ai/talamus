import { useEffect, useRef, useState } from "react";
import { api, SearchHitLite } from "../api";

/** Instant search in the sidebar: plain search as you type (zero LLM), an
 * optional "expand with AI" pass (one cached LLM call), Enter opens the top
 * hit, a click opens that note in the inspector. */
export function SearchBar() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHitLite[]>([]);
  const [expanding, setExpanding] = useState(false);
  const [note, setNoteMsg] = useState("");
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    if (!q.trim()) {
      setHits([]);
      setNoteMsg("");
      return;
    }
    timer.current = window.setTimeout(() => {
      api
        .searchNotes(q)
        .then((r) => setHits(r.data?.hits ?? []))
        .catch(() => setHits([]));
    }, 180);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [q]);

  const openNote = (title: string) => {
    window.dispatchEvent(new CustomEvent("talamus:openNote", { detail: { title } }));
    setQ("");
    setHits([]);
    setNoteMsg("");
  };

  const smart = async () => {
    if (!q.trim() || expanding) return;
    setExpanding(true);
    setNoteMsg("");
    try {
      const r = await api.smartSearch(q);
      setHits(r.data?.hits ?? []);
      setNoteMsg(r.expanded ? "expanded with AI" : "");
    } catch {
      setNoteMsg("AI expansion failed — showing plain results");
    } finally {
      setExpanding(false);
    }
  };

  return (
    <div style={{ padding: "0 12px 10px", position: "relative" }}>
      <input
        value={q}
        placeholder="Search notes…"
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && hits.length) openNote(hits[0].title);
          if (e.key === "Escape") {
            setQ("");
            setHits([]);
          }
        }}
        style={{ width: "100%", fontSize: 13 }}
      />
      {q.trim() ? (
        <div
          style={{
            position: "absolute",
            zIndex: 40,
            left: 12,
            right: 12,
            marginTop: 4,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
            maxHeight: 320,
            overflowY: "auto",
          }}
        >
          {hits.map((h) => (
            <button
              key={h.title}
              onClick={() => openNote(h.title)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "8px 10px",
                background: "transparent",
                border: "none",
                borderBottom: "1px solid var(--border)",
                cursor: "pointer",
                color: "var(--text)",
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 500 }}>{h.title}</div>
              {h.summary ? (
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--muted)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h.summary}
                </div>
              ) : null}
            </button>
          ))}
          {!hits.length ? (
            <div style={{ padding: "8px 10px", fontSize: 12, color: "var(--muted)" }}>
              no instant matches
            </div>
          ) : null}
          <button
            onClick={() => void smart()}
            disabled={expanding}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "8px 10px",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--accent-2)",
              fontSize: 12,
            }}
          >
            {expanding ? "expanding with AI…" : "✨ expand with AI (1 LLM call, cached)"}
          </button>
          {note ? (
            <div style={{ padding: "0 10px 8px", fontSize: 11, color: "var(--muted)" }}>{note}</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
