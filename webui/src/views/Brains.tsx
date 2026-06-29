import { useEffect, useState } from "react";
import { ActiveBrain, api, BrainItem, BrainList } from "../api";

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 16,
};

type Outcome = { success: boolean; message?: string };
type Switch = (body: { name?: string; path?: string }) => Promise<Outcome>;
type Init = (body: { path: string; name?: string }) => Promise<Outcome>;

function Section({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        color: "var(--accent-2)",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: 0.8,
        textTransform: "uppercase",
        margin: "18px 0 8px",
      }}
    >
      {children}
    </div>
  );
}

function Badge({
  text,
  color,
  bg,
  border,
}: {
  text: string;
  color: string;
  bg: string;
  border: string;
}) {
  return (
    <span
      style={{
        fontSize: 11,
        color,
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: 999,
        padding: "2px 9px",
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}

function BrainCard({
  b,
  isActive,
  busy,
  onOpen,
}: {
  b: BrainItem;
  isActive: boolean;
  busy: boolean;
  onOpen: () => void;
}) {
  return (
    <div
      style={{
        ...panel,
        borderLeft: `2px solid ${isActive ? "var(--accent)" : "var(--border)"}`,
        marginBottom: 10,
      }}
    >
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontWeight: 500 }}>{b.name}</span>
        {isActive ? (
          <Badge text="active" color="var(--accent-2)" bg="rgba(110,91,255,0.16)" border="rgba(110,91,255,0.45)" />
        ) : null}
        <Badge text={b.type} color="var(--muted)" bg="var(--surface-2)" border="var(--border)" />
        {b.federated ? (
          <Badge text="federated" color="var(--accent-2)" bg="rgba(79,195,247,0.12)" border="rgba(79,195,247,0.35)" />
        ) : null}
        {b.sensitive ? (
          <Badge text="sensitive" color="var(--warn)" bg="rgba(255,183,77,0.13)" border="rgba(255,183,77,0.35)" />
        ) : null}
        {!b.exists ? (
          <Badge text="missing" color="var(--danger)" bg="rgba(255,138,138,0.12)" border="rgba(255,138,138,0.4)" />
        ) : null}
        <span style={{ flex: 1 }} />
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{b.notes} notes</span>
        {isActive ? (
          <span style={{ color: "var(--muted)", fontSize: 12, fontStyle: "italic" }}>current</span>
        ) : (
          <button className="btn" onClick={onOpen} disabled={busy || !b.exists} style={{ fontSize: 12 }}>
            Open
          </button>
        )}
      </div>
      <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6, wordBreak: "break-all" }}>
        {b.path}
      </div>
    </div>
  );
}

export function Brains({
  active,
  onSwitch,
  onInit,
}: {
  active?: ActiveBrain | null;
  onSwitch?: Switch;
  onInit?: Init;
}) {
  const [d, setD] = useState<BrainList | null>(null);
  const [folder, setFolder] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .brains()
      .then((r) => setD(r.data))
      .catch(() => setD(null));
  }, []);

  // On success the shell remounts (App bumps its key), so this component unmounts —
  // the finally still clears busy defensively if anything goes wrong.
  const runAction = async (fn: () => Promise<Outcome> | undefined) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      if (r && !r.success) setError(r.message ?? "Could not switch brain.");
    } catch {
      setError("Could not reach the brain.");
    } finally {
      setBusy(false);
    }
  };

  const doSwitch = (body: { name?: string; path?: string }) => runAction(() => onSwitch?.(body));
  const doInit = () => folder.trim() && runAction(() => onInit?.({ path: folder.trim() }));

  if (!d) return <div style={{ color: "var(--muted)" }}>Loading…</div>;

  const isActive = (b: BrainItem) => !!active && b.name === active.name;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Brains</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        Switch the brain the workbench is pointed at — like opening a different vault.
      </div>

      <div style={{ ...panel, borderLeft: "3px solid var(--accent)" }}>
        <Section>Open or create a brain</Section>
        <input
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && doSwitch({ path: folder.trim() })}
          placeholder="Path to a brain folder…"
          style={{
            width: "100%",
            background: "var(--bg)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "9px 12px",
            font: "inherit",
            fontSize: 13,
          }}
        />
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
          <button
            className="btn btn-primary"
            onClick={() => doSwitch({ path: folder.trim() })}
            disabled={busy || !folder.trim()}
          >
            {busy ? "Working…" : "Open"}
          </button>
          <button className="btn" onClick={doInit} disabled={busy || !folder.trim()}>
            Create new brain here
          </button>
        </div>
        <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
          <strong>Open</strong> an existing brain (it has <code>talamus.json</code>), or{" "}
          <strong>create</strong> a new one in any folder — it’s scaffolded and remembered in the
          registry.
        </div>
        {error ? (
          <div style={{ color: "var(--danger)", fontSize: 13, marginTop: 8 }}>{error}</div>
        ) : null}
      </div>

      <Section>Registered {d.brains.length ? `(${d.brains.length})` : ""}</Section>
      {d.brains.length === 0 ? (
        <div style={{ ...panel, color: "var(--muted)", fontSize: 13 }}>
          No brains registered yet. <code>talamus init</code> registers one; each is a local
          folder of Markdown notes.
        </div>
      ) : (
        d.brains.map((b) => (
          <BrainCard
            key={b.id}
            b={b}
            isActive={isActive(b)}
            busy={busy}
            onOpen={() => doSwitch({ name: b.name })}
          />
        ))
      )}

      {d.unregistered.length ? (
        <>
          <Section>Unregistered ({d.unregistered.length})</Section>
          {d.unregistered.map((u) => (
            <div key={u.path} style={{ ...panel, marginBottom: 10 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ fontWeight: 500 }}>{u.name}</span>
                <span style={{ flex: 1 }} />
                <button
                  className="btn"
                  onClick={() => doSwitch({ path: u.path })}
                  disabled={busy}
                  style={{ fontSize: 12 }}
                >
                  Open
                </button>
              </div>
              <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4, wordBreak: "break-all" }}>
                {u.path}
              </div>
            </div>
          ))}
        </>
      ) : null}
    </div>
  );
}
