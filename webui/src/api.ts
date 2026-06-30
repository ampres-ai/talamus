export type ServiceResult<T> = {
  success: boolean;
  message?: string;
  code?: string;
  data: T;
};

export type GraphNode = {
  id: string;
  label: string;
  x: number;
  y: number;
  r: number;
  degree: number;
};

export type GraphEdge = { source: string; target: string; type: string; typed: boolean };

export type GraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width: number;
  height: number;
  total?: number;
  shown?: number;
};

export type NoteSummary = { title: string; summary: string };

export type NoteDetail = { title: string; found: boolean; markdown: string | null };

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

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
  return (await resp.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
  return (await resp.json()) as T;
}

export const api = {
  readiness: () => get<ServiceResult<Record<string, unknown>>>("/api/readiness"),
  library: () => get<ServiceResult<{ notes: NoteSummary[] }>>("/api/library"),
  graph: () => get<ServiceResult<GraphData>>("/api/graph"),
  note: (title: string) =>
    get<ServiceResult<NoteDetail>>(`/api/note?title=${encodeURIComponent(title)}`),
  review: (status = "pending") =>
    get<ServiceResult<ReviewItem[]>>(`/api/review?status=${encodeURIComponent(status)}`),
  applyReview: (id: string) =>
    post<ServiceResult<ReviewItem>>(`/api/review/${encodeURIComponent(id)}/apply`),
  rejectReview: (id: string, reason = "") =>
    post<ServiceResult<ReviewItem>>(`/api/review/${encodeURIComponent(id)}/reject`, { reason }),
  ask: (question: string) => post<ServiceResult<AskResult>>("/api/ask", { question }),
  diagnostics: () => get<ServiceResult<Diagnostics>>("/api/diagnostics"),
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
