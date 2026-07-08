export type ServiceResult<T> = {
  success: boolean;
  message?: string;
  code?: string;
  data: T;
};

export type GraphNode = { id: string; label: string; degree: number };

export type GraphEdge = { source: string; target: string; type: string; typed: boolean };

export type GraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total?: number;
  shown?: number;
};

export type NoteSummary = { title: string; summary: string };

export type NoteDetail = {
  title: string;
  found: boolean;
  markdown: string | null;
  as_of?: string;
  version?: Record<string, unknown> | null;
};

export type VerifyResult = {
  title: string;
  found: boolean;
  checked: boolean;
  ok: boolean;
  summary: string;
  body: string;
};

export type IngestPreview = {
  target: string;
  target_type: string;
  chars: number;
  chunks: number;
  est_llm_calls: number;
  est_input_tokens: number;
  requires_confirmation: boolean;
};

export type IngestRunResult = {
  target: string;
  notes_written: number;
  source: string;
  files: number | null;
  skipped: number | null;
  chunks: number | null;
};

export type ScanPreview = {
  target_root: string;
  profile: string;
  files: number;
  skipped: number;
  total_bytes: number;
  est_tokens: number;
  est_llm_calls: number;
  secret_files: string[];
};

export type ScanActionResult = {
  target_root: string;
  state: string;
  files: number;
  notes_written: number;
};

export type ReviewItem = {
  item_id: string;
  kind: string;
  title: string;
  status: string;
  created_at: string;
  resolved_at: string;
  resolution: string;
  detail: Record<string, unknown>;
};

export type BrainItem = {
  id: string;
  name: string;
  path: string;
  type: string;
  federated: boolean;
  sensitive: boolean;
  selected: boolean;
  exists: boolean;
  notes: number;
  created_at: string;
  updated_at: string;
  last_accessed_at: string;
  project: Record<string, unknown> | null;
};

export type UnregisteredBrain = { name: string; path: string; register_command: string };

export type BrainList = {
  registry_path: string;
  selected: string;
  brains: BrainItem[];
  unregistered: UnregisteredBrain[];
};

export type ActiveBrain = { path: string; name: string; initialized: boolean; notes: number };

export type DiagnosticCheck = {
  check_id: string;
  label: string;
  status: string;
  message: string;
  detail: string;
  action: string;
};

export type Diagnostics = {
  root: string;
  ok: boolean;
  storage_provider: string;
  pdf_converter: string;
  ocr_provider: string;
  ocr_model: string;
  llm_provider: string;
  llm_status: string;
  graph_provider: string;
  search_provider: string;
  notes: number;
  index_backend: string;
  index_bytes: number;
  overview_built: boolean;
  overview_domains: number;
  cache_current: boolean;
  checks: DiagnosticCheck[];
};

export type OntologyStatus = {
  schema_id: string;
  version: number;
  types: Record<string, number>;
  coverage: { edges?: number; non_related?: number; non_related_share?: number };
};

export type OntologyType = {
  id: string;
  name: string;
  definition: string;
  inverse: string;
  surfaces: string[];
  examples: string[];
  support: number;
  distinct_notes: number;
  confidence: number;
  status: string;
  valid_from: string;
  valid_to: string;
};

export type AskSource = { title: string; summary: string };

export type AskResult = {
  question: string;
  answer: string;
  answered: boolean;
  engine: string;
  route: string;
  context_tokens: number;
  notice: string;
  sources: AskSource[];
};

export type EngineReadiness = {
  provider: string;
  label: string;
  command: string;
  available: boolean;
  configured: boolean;
  needs_secret: boolean;
  status: string;
  detail: string;
};

export type Readiness = {
  root: string;
  scope: string;
  source: string;
  config_exists: boolean;
  config_error: string;
  selected_engine: string;
  selected_model: string;
  engines: EngineReadiness[];
};

export type IntegrationReport = {
  root: string;
  mcp_config_path: string;
  mcp_installed: boolean;
  hook_command: string;
  cursor_installed: boolean;
  codex_on_path: boolean;
  hook_installed: boolean;
};

export type McpInstallReport = {
  agent: string;
  results: Record<string, ServiceResult<Record<string, unknown>>>;
};

export type HookInstallReport = {
  settings_path: string;
  command: string;
  installed: boolean;
  already_installed: boolean;
};

export type EngineProbeResult = {
  engine: string;
  verified: boolean;
  answer?: string;
  error?: string;
  hint: string;
  limit_reached: boolean;
};

export let pendingAskQuery: string | null = null;

export function setPendingAskQuery(query: string | null) {
  pendingAskQuery = query && query.trim() ? query.trim() : null;
}

// The per-launch workbench token, injected into index.html by the server. It is
// sent on every /api call so a cross-origin page (which cannot read this token)
// cannot drive the local API. See dev/ROADMAP.md Phase S1.
const UI_TOKEN =
  document.querySelector('meta[name="talamus-ui-token"]')?.getAttribute("content") ?? "";

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(path, { headers: { "X-Talamus-UI": UI_TOKEN } });
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
  return (await resp.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Talamus-UI": UI_TOKEN },
    body: JSON.stringify(body ?? {}),
  });
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
  return (await resp.json()) as T;
}

export const api = {
  readiness: () => get<ServiceResult<Readiness>>("/api/readiness"),
  library: () => get<ServiceResult<{ notes: NoteSummary[] }>>("/api/library"),
  graph: () => get<ServiceResult<GraphData>>("/api/graph"),
  note: (title: string, asOf = "") =>
    get<ServiceResult<NoteDetail>>(
      `/api/note?title=${encodeURIComponent(title)}${asOf ? `&as_of=${encodeURIComponent(asOf)}` : ""}`,
    ),
  verify: (title: string) => post<ServiceResult<VerifyResult>>("/api/verify", { title }),
  importVault: (directory: string) =>
    post<ServiceResult<Record<string, unknown>>>("/api/import/vault", { directory }),
  review: (status = "pending") =>
    get<ServiceResult<ReviewItem[]>>(`/api/review?status=${encodeURIComponent(status)}`),
  applyReview: (id: string) =>
    post<ServiceResult<ReviewItem>>(`/api/review/${encodeURIComponent(id)}/apply`),
  rejectReview: (id: string, reason = "") =>
    post<ServiceResult<ReviewItem>>(`/api/review/${encodeURIComponent(id)}/reject`, { reason }),
  ask: (question: string) => post<ServiceResult<AskResult>>("/api/ask", { question }),
  diagnostics: () => get<ServiceResult<Diagnostics>>("/api/diagnostics"),
  integrations: () => get<ServiceResult<IntegrationReport>>("/api/integrations"),
  connectAgent: (agent: string) =>
    post<ServiceResult<McpInstallReport>>("/api/integrations/mcp", { agent }),
  installHook: () => post<ServiceResult<HookInstallReport>>("/api/integrations/hook"),
  probeEngine: (engine: string) =>
    post<ServiceResult<EngineProbeResult>>("/api/engines/probe", { engine }),
  brains: () => get<ServiceResult<BrainList>>("/api/brains"),
  getActive: () => get<ServiceResult<ActiveBrain>>("/api/active"),
  setActiveBrain: (body: { name?: string; path?: string }) =>
    post<ServiceResult<ActiveBrain>>("/api/active", body),
  initBrain: (body: { path: string; name?: string }) =>
    post<ServiceResult<BrainItem>>("/api/brains/init", body),
  ontologyStatus: () => get<ServiceResult<OntologyStatus>>("/api/ontology/status"),
  ontologyTypes: (status = "candidate") =>
    get<ServiceResult<OntologyType[]>>(`/api/ontology/types?status=${encodeURIComponent(status)}`),
  promoteOntology: (id: string) =>
    post<ServiceResult<unknown>>(`/api/ontology/${encodeURIComponent(id)}/promote`),
  rejectOntology: (id: string, reason = "") =>
    post<ServiceResult<unknown>>(`/api/ontology/${encodeURIComponent(id)}/reject`, { reason }),
  importPreview: (target: string) =>
    post<ServiceResult<IngestPreview>>("/api/import/preview", { target }),
  importRun: (target: string, confirmed: boolean) =>
    post<ServiceResult<IngestPreview | IngestRunResult>>("/api/import/run", { target, confirmed }),
  importText: (text: string) => post<ServiceResult<IngestRunResult>>("/api/import/text", { text }),
  scanPreview: (target: string) =>
    post<ServiceResult<ScanPreview>>("/api/scan/preview", { target }),
  scanRun: (target: string, confirmed: boolean, allow_secrets: boolean) =>
    post<ServiceResult<ScanPreview | ScanActionResult>>("/api/scan/run", {
      target,
      confirmed,
      allow_secrets,
    }),
};
