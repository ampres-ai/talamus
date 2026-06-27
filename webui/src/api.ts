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
};
