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
type ErrorInfo = { path: string; message: string };

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

function ErrorCard({ error }: { error: ErrorInfo }) {
  return (
    <div style={{ ...panel, borderColor: "var(--danger)", color: "var(--danger)", fontSize: 13 }}>
      <div style={{ fontWeight: 600 }}>Could not load this card.</div>
      <div style={{ marginTop: 6, wordBreak: "break-all" }}>{error.path}</div>
      <div style={{ marginTop: 4, color: "var(--muted)" }}>{error.message}</div>
    </div>
  );
}

function LoadingSkeleton({ label }: { label: string }) {
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {[0, 1, 2].map((i) => (
        <div key={i} style={{ ...panel, padding: 12, color: "var(--muted)", fontSize: 13 }}>
          {label}...
        </div>
      ))}
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <div style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.5 }}>{children}</div>;
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
  onProbe,
}: {
  engine: EngineReadiness;
  active: boolean;
  probing: boolean;
  result?: ServiceResult<EngineProbeResult>;
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
        <button className="btn" onClick={onProbe} disabled={probing} style={{ fontSize: 12 }}>
          {probing ? "Probing..." : "Probe"}
        </button>
      </div>
      <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6, wordBreak: "break-all" }}>
        {engine.detail || "No readiness detail returned."}
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

function agentBadge(agent: string, installed: boolean) {
  if (agent === "codex") return installed ? "on PATH" : "missing";
  return installed ? "installed" : "missing";
}

export function Connect() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationReport | null>(null);
  const [engineLoading, setEngineLoading] = useState(true);
  const [agentLoading, setAgentLoading] = useState(true);
  const [engineError, setEngineError] = useState<ErrorInfo | null>(null);
  const [agentError, setAgentError] = useState<ErrorInfo | null>(null);
  const [probeResults, setProbeResults] = useState<Record<string, ServiceResult<EngineProbeResult>>>({});
  const [probing, setProbing] = useState<string | null>(null);
  const [busyAgent, setBusyAgent] = useState<string | null>(null);
  const [hookResult, setHookResult] = useState<ResultLine | null>(null);

  const loadEngines = async () => {
    setEngineLoading(true);
    setEngineError(null);
    try {
      const ready = await api.readiness();
      if (ready.success && ready.data) setReadiness(ready.data);
      else {
        setReadiness(null);
        setEngineError({ path: "/api/readiness", message: ready.message ?? "Engine readiness did not load." });
      }
    } catch (error) {
      setReadiness(null);
      setEngineError({ path: "/api/readiness", message: messageFromError(error, "Engine readiness fetch failed.") });
    } finally {
      setEngineLoading(false);
    }
  };

  const loadIntegrations = async () => {
    setAgentLoading(true);
    setAgentError(null);
    try {
      const status = await api.integrations();
      if (status.success && status.data) setIntegrations(status.data);
      else {
        setIntegrations(null);
        setAgentError({ path: "/api/integrations", message: status.message ?? "Integration status did not load." });
      }
    } catch (error) {
      setIntegrations(null);
      setAgentError({ path: "/api/integrations", message: messageFromError(error, "Integration status fetch failed.") });
    } finally {
      setAgentLoading(false);
    }
  };

  useEffect(() => {
    void loadEngines();
    void loadIntegrations();
  }, []);

  const probeEngine = async (provider: string) => {
    setProbing(provider);
    setEngineError(null);
    try {
      const result = await api.probeEngine(provider);
      setProbeResults((current) => ({ ...current, [provider]: result }));
    } catch (error) {
      setEngineError({ path: "/api/engines/probe", message: messageFromError(error, "Could not probe engine.") });
    } finally {
      setProbing(null);
    }
  };

  const connectAgent = async (agent: string) => {
    setBusyAgent(agent);
    setAgentError(null);
    try {
      const result = await api.connectAgent(agent);
      if (!result.success) {
        setAgentError({ path: "/api/integrations/mcp", message: result.message ?? "Could not connect agent." });
      }
      await loadIntegrations();
    } catch (error) {
      setAgentError({ path: "/api/integrations/mcp", message: messageFromError(error, "Could not connect agent.") });
    } finally {
      setBusyAgent(null);
    }
  };

  const installHook = async () => {
    setBusyAgent("hook");
    setHookResult(null);
    setAgentError(null);
    try {
      const result = await api.installHook();
      setHookResult({ ok: result.success, message: result.message ?? "Hook install finished." });
      await loadIntegrations();
    } catch (error) {
      setHookResult({ ok: false, message: messageFromError(error, "Could not install hook.") });
      setAgentError({ path: "/api/integrations/hook", message: messageFromError(error, "Could not install hook.") });
    } finally {
      setBusyAgent(null);
    }
  };

  const engines = readiness?.engines ?? [];

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Connect</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, margin: "6px 0 16px" }}>
        Inspect local engines and connect local agents to this brain.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14 }}>
        <div style={panel}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>Engine</h3>
            <span style={{ flex: 1 }} />
            {readiness?.selected_model ? <Badge>{readiness.selected_model}</Badge> : null}
          </div>
          <Section>Configured engines</Section>
          {engineLoading ? <LoadingSkeleton label="Loading engine" /> : null}
          {!engineLoading && engineError ? <ErrorCard error={engineError} /> : null}
          {!engineLoading && !engineError && readiness && engines.length === 0 ? (
            <EmptyState>No engines were returned by /api/readiness.</EmptyState>
          ) : null}
          {!engineLoading && !engineError && readiness && engines.length > 0
            ? engines.map((engine) => (
                <EngineRow
                  key={engine.provider}
                  engine={engine}
                  active={engine.configured || engine.provider === readiness.selected_engine}
                  probing={probing === engine.provider}
                  result={probeResults[engine.provider]}
                  onProbe={() => void probeEngine(engine.provider)}
                />
              ))
            : null}
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
          {agentLoading ? <LoadingSkeleton label="Loading integration" /> : null}
          {!agentLoading && agentError ? <ErrorCard error={agentError} /> : null}
          {!agentLoading && !agentError && !integrations ? (
            <EmptyState>No integration status was returned by /api/integrations.</EmptyState>
          ) : null}
          {!agentLoading && !agentError && integrations
            ? AGENTS.map((agent) => {
                const installed = agentInstalled(agent.id, integrations);
                return (
                  <div key={agent.id} style={{ ...panel, padding: 12, marginBottom: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <Dot tone={installed ? "var(--ok)" : "var(--muted)"} />
                      <span style={{ fontWeight: 500 }}>{agent.label}</span>
                      <Badge tone={installed ? "var(--ok)" : "var(--muted)"}>
                        {agentBadge(agent.id, installed)}
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
            : null}

          <Section>Session capture hook</Section>
          <div style={{ ...panel, padding: 12 }}>
            {agentLoading ? <EmptyState>Loading hook status...</EmptyState> : null}
            {!agentLoading && integrations?.hook_installed ? (
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
            ) : null}
            {!agentLoading && integrations && !integrations.hook_installed ? (
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
            ) : null}
            {!agentLoading && !integrations ? <EmptyState>Hook status is unavailable.</EmptyState> : null}
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