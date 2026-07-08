import { CheckCircle } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import {
  api,
  EngineProbeResult,
  EngineReadiness,
  IntegrationReport,
  Readiness,
  ServiceResult,
} from "../api";

const panel: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 16,
};

type ResultLine = { ok: boolean; message: string };

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

function Dot({ tone }: { tone: string }) {
  return (
    <span
      style={{
        width: 9,
        height: 9,
        borderRadius: "50%",
        background: tone,
        boxShadow: tone === "var(--ok)" ? `0 0 6px ${tone}` : undefined,
        flexShrink: 0,
      }}
    />
  );
}

function Badge({ children, tone = "var(--muted)" }: { children: React.ReactNode; tone?: string }) {
  return (
    <span
      style={{
        color: tone,
        background: "var(--surface-2)",
        border: "1px solid var(--border)",
        borderRadius: 999,
        padding: "2px 8px",
        fontSize: 11,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

function messageFromError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function probeMessage(result: ServiceResult<EngineProbeResult>) {
  if (result.data?.verified) {
    const answer = result.data.answer?.trim();
    return answer ? `verified: ${answer.slice(0, 120)}` : result.message ?? "verified";
  }
  return result.data?.hint || result.message || "Probe failed.";
}

function EngineRow({
  engine,
  active,
  probing,
  result,
  onSelect,
  onProbe,
}: {
  engine: EngineReadiness;
  active: boolean;
  probing: boolean;
  result?: ServiceResult<EngineProbeResult>;
  onSelect: () => void;
  onProbe: () => void;
}) {
  const tone = active ? "var(--accent)" : engine.available ? "var(--ok)" : "var(--muted)";
  return (
    <div
      style={{
        ...panel,
        padding: 12,
        borderLeft: `3px solid ${tone}`,
        marginBottom: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Dot tone={engine.available ? "var(--ok)" : "var(--muted)"} />
        <div style={{ minWidth: 160 }}>
          <div style={{ fontWeight: 500 }}>{engine.label}</div>
          <div style={{ color: "var(--muted)", fontSize: 12 }}>{engine.provider}</div>
        </div>
        {active ? <Badge tone="var(--accent-2)">active</Badge> : null}
        <Badge>{engine.status}</Badge>
        {engine.needs_secret ? <Badge tone="var(--warn)">needs secret</Badge> : null}
        <span style={{ flex: 1 }} />
        {active ? (
          <span style={{ color: "var(--muted)", fontSize: 12, fontStyle: "italic" }}>selected</span>
        ) : (
          <button className="btn" onClick={onSelect} style={{ fontSize: 12 }}>
            Select
          </button>
        )}
        <button className="btn" onClick={onProbe} disabled={probing} style={{ fontSize: 12 }}>
          {probing ? "Probing..." : "Probe"}
        </button>
      </div>
      <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6, wordBreak: "break-all" }}>
        {engine.detail}
      </div>
      {result ? (
        <div
          style={{
            color: result.data?.verified
              ? "var(--ok)"
              : result.data?.limit_reached
                ? "var(--warn)"
                : "var(--danger)",
            fontSize: 12.5,
            marginTop: 8,
          }}
        >
          {result.data?.verified ? <CheckCircle size={14} weight="fill" style={{ verticalAlign: "-2px" }} /> : null}
          {result.data?.limit_reached ? <Badge tone="var(--warn)">rate limited</Badge> : null} {probeMessage(result)}
        </div>
      ) : null}
    </div>
  );
}

const AGENTS = [
  { id: "claude", label: "Claude Code" },
  { id: "cursor", label: "Cursor" },
  { id: "codex", label: "codex" },
];

function agentInstalled(agent: string, integrations: IntegrationReport) {
  if (agent === "claude") return integrations.mcp_installed;
  if (agent === "cursor") return integrations.cursor_installed;
  return integrations.codex_on_path;
}

export function Connect() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationReport | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [probeResults, setProbeResults] = useState<Record<string, ServiceResult<EngineProbeResult>>>({});
  const [probing, setProbing] = useState<string | null>(null);
  const [busyAgent, setBusyAgent] = useState<string | null>(null);
  const [hookResult, setHookResult] = useState<ResultLine | null>(null);

  const load = async () => {
    try {
      const [ready, status] = await Promise.all([api.readiness(), api.integrations()]);
      if (ready.success) setReadiness(ready.data);
      else setEngineError(ready.message ?? "Could not load engines.");
      if (status.success) setIntegrations(status.data);
      else setAgentError(status.message ?? "Could not load integrations.");
    } catch (error) {
      const message = messageFromError(error, "Could not load Connect.");
      setEngineError(message);
      setAgentError(message);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const selectEngine = async (provider: string) => {
    setEngineError(null);
    try {
      const result = await api.updateEngineSettings(provider);
      if (!result.success) {
        setEngineError(result.message ?? "Could not select engine.");
        return;
      }
      const ready = await api.readiness();
      if (ready.success) setReadiness(ready.data);
      else setEngineError(ready.message ?? "Could not refresh engines.");
    } catch (error) {
      setEngineError(messageFromError(error, "Could not select engine."));
    }
  };

  const probeEngine = async (provider: string) => {
    setProbing(provider);
    setEngineError(null);
    try {
      const result = await api.probeEngine(provider);
      setProbeResults((current) => ({ ...current, [provider]: result }));
    } catch (error) {
      setEngineError(messageFromError(error, "Could not probe engine."));
    } finally {
      setProbing(null);
    }
  };

  const connectAgent = async (agent: string) => {
    setBusyAgent(agent);
    setAgentError(null);
    try {
      const result = await api.connectAgent(agent);
      if (!result.success) setAgentError(result.message ?? "Could not connect agent.");
      const status = await api.integrations();
      if (status.success) setIntegrations(status.data);
      else setAgentError(status.message ?? "Could not refresh integrations.");
    } catch (error) {
      setAgentError(messageFromError(error, "Could not connect agent."));
    } finally {
      setBusyAgent(null);
    }
  };

  const installHook = async () => {
    setBusyAgent("hook");
    setHookResult(null);
    try {
      const result = await api.installHook();
      setHookResult({ ok: result.success, message: result.message ?? "Hook install finished." });
      const status = await api.integrations();
      if (status.success) setIntegrations(status.data);
    } catch (error) {
      setHookResult({ ok: false, message: messageFromError(error, "Could not install hook.") });
    } finally {
      setBusyAgent(null);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Connect</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        Choose the engine and connect local agents to this brain.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14 }}>
        <div style={panel}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>Engine</h3>
            <span style={{ flex: 1 }} />
            {readiness?.selected_model ? <Badge>{readiness.selected_model}</Badge> : null}
          </div>
          <Section>Configured engines</Section>
          {readiness ? (
            readiness.engines.map((engine) => (
              <EngineRow
                key={engine.provider}
                engine={engine}
                active={engine.configured || engine.provider === readiness.selected_engine}
                probing={probing === engine.provider}
                result={probeResults[engine.provider]}
                onSelect={() => void selectEngine(engine.provider)}
                onProbe={() => void probeEngine(engine.provider)}
              />
            ))
          ) : (
            <div style={{ color: "var(--muted)", fontSize: 13 }}>Loading...</div>
          )}
          {engineError ? <div style={{ color: "var(--danger)", fontSize: 13 }}>{engineError}</div> : null}
        </div>

        <div style={panel}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>Agents</h3>
            <span style={{ flex: 1 }} />
            <button className="btn btn-primary" onClick={() => void connectAgent("auto")} disabled={!!busyAgent}>
              {busyAgent === "auto" ? "Connecting..." : "Connect all detected"}
            </button>
          </div>

          <Section>MCP</Section>
          {integrations ? (
            AGENTS.map((agent) => {
              const installed = agentInstalled(agent.id, integrations);
              return (
                <div key={agent.id} style={{ ...panel, padding: 12, marginBottom: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <Dot tone={installed ? "var(--ok)" : "var(--muted)"} />
                    <span style={{ fontWeight: 500 }}>{agent.label}</span>
                    <Badge tone={installed ? "var(--ok)" : "var(--muted)"}>
                      {installed ? "installed" : "missing"}
                    </Badge>
                    <span style={{ flex: 1 }} />
                    <button
                      className="btn"
                      onClick={() => void connectAgent(agent.id)}
                      disabled={!!busyAgent}
                      style={{ fontSize: 12 }}
                    >
                      {busyAgent === agent.id ? "Connecting..." : "Connect"}
                    </button>
                  </div>
                </div>
              );
            })
          ) : (
            <div style={{ color: "var(--muted)", fontSize: 13 }}>Loading...</div>
          )}
          {agentError ? <div style={{ color: "var(--danger)", fontSize: 13 }}>{agentError}</div> : null}

          <Section>Session capture hook</Section>
          <div style={{ ...panel, padding: 12 }}>
            {integrations?.hook_installed ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <Dot tone="var(--ok)" />
                  <span style={{ fontWeight: 500 }}>Hook installed</span>
                  <Badge tone="var(--ok)">active</Badge>
                </div>
                <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6, wordBreak: "break-all" }}>
                  {integrations.root}/.claude/settings.json
                </div>
              </>
            ) : (
              <>
                <div style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.5 }}>
                  what is captured: session transcript + git diff; the worth-remembering gate; stored only in THIS
                  brain; audit at .talamus/logs/capture.log
                </div>
                <button
                  className="btn"
                  onClick={() => void installHook()}
                  disabled={!!busyAgent}
                  style={{ marginTop: 10, fontSize: 12 }}
                >
                  {busyAgent === "hook" ? "Installing..." : "Install hook"}
                </button>
              </>
            )}
            {hookResult ? (
              <div
                style={{
                  color: hookResult.ok ? "var(--ok)" : "var(--danger)",
                  fontSize: 12.5,
                  marginTop: 8,
                }}
              >
                {hookResult.message}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}