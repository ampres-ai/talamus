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

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
  return (await resp.json()) as T;
}

export const api = {
  readiness: () => get<ServiceResult<Record<string, unknown>>>("/api/readiness"),
  library: () => get<ServiceResult<{ notes: NoteSummary[] }>>("/api/library"),
  graph: () => get<ServiceResult<GraphData>>("/api/graph"),
};
