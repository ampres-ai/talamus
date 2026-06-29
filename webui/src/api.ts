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
};

export type NoteSummary = { title: string; summary: string };

export type NoteDetail = { title: string; found: boolean; markdown: string | null };

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
  ontologyStatus: () => get<ServiceResult<OntologyStatus>>("/api/ontology/status"),
  ontologyTypes: (status = "candidate") =>
    get<ServiceResult<OntologyType[]>>(`/api/ontology/types?status=${encodeURIComponent(status)}`),
  promoteOntology: (id: string) =>
    post<ServiceResult<unknown>>(`/api/ontology/${encodeURIComponent(id)}/promote`),
  rejectOntology: (id: string, reason = "") =>
    post<ServiceResult<unknown>>(`/api/ontology/${encodeURIComponent(id)}/reject`, { reason }),
};
