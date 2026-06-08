import type {
  StatsResponse,
  PapersResponse,
  PaperDetail,
  RelatedPapersResponse,
  SearchRequest,
  SearchResponse,
  TechniquesResponse,
  GraphResponse,
  ClustersResponse,
  ChatRequest,
  ChatResponse,
} from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${path}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  stats: () => apiFetch<StatsResponse>("/stats"),

  papers: (params: Record<string, string | number | undefined>) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") p.set(k, String(v));
    }
    return apiFetch<PapersResponse>(`/papers?${p.toString()}`);
  },

  paper: (id: string) => apiFetch<PaperDetail>(`/papers/${id}`),

  paperRelated: (id: string, limit = 8) =>
    apiFetch<RelatedPapersResponse>(
      `/papers/${id}/related?limit=${limit}`
    ),

  search: (body: SearchRequest) =>
    apiFetch<SearchResponse>("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  techniques: (q?: string) =>
    apiFetch<TechniquesResponse>(
      `/techniques${q ? `?q=${encodeURIComponent(q)}&per_page=50` : "?per_page=50"}`
    ),

  graph: (minWeight = 1.5, cluster?: number) => {
    const p = new URLSearchParams({ min_weight: String(minWeight) });
    if (cluster !== undefined) p.set("cluster", String(cluster));
    return apiFetch<GraphResponse>(`/graph?${p.toString()}`);
  },

  graphClusters: () => apiFetch<ClustersResponse>("/graph/clusters"),

  chat: (body: ChatRequest) =>
    apiFetch<ChatResponse>("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

export const queryKeys = {
  stats: ["stats"] as const,
  papers: (p: Record<string, unknown>) => ["papers", p] as const,
  paper: (id: string) => ["paper", id] as const,
  paperRelated: (id: string) => ["paper", id, "related"] as const,
  search: (q: string, f: unknown) => ["search", q, f] as const,
  techniques: (q: string) => ["techniques", q] as const,
  graph: (minWeight: number, cluster?: number) =>
    ["graph", minWeight, cluster] as const,
  graphClusters: ["graph", "clusters"] as const,
};
