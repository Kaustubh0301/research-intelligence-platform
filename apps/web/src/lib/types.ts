export interface ConferenceStat {
  short_name: string;
  year: number;
  count: number;
}

export interface ClusterStat {
  cluster_id: number;
  paper_count: number;
  avg_degree: number;
  avg_betweenness: number;
}

export interface TechniqueStat {
  canonical_name: string;
  paper_count: number;
}

export interface TopPaper {
  id: string;
  title: string;
  citation_count: number;
  conference: string | null;
  year: number | null;
  presentation_type: string | null;
  cluster_id: number | null;
  degree_centrality: number;
}

export interface StatsResponse {
  total_papers: number;
  total_edges: number;
  total_techniques: number;
  total_clusters: number;
  conferences: ConferenceStat[];
  clusters: ClusterStat[];
  top_techniques: TechniqueStat[];
  top_papers: TopPaper[];
}

export interface PaperSummary {
  id: string;
  title: string;
  year: number;
  conference: string | null;
  presentation_type: string | null;
  citation_count: number;
  influential_citation_count: number;
  is_open_access: boolean;
  has_pdf: boolean;
  abstract_snippet: string | null;
  pdf_url: string | null;
  arxiv_id: string | null;
  openreview_id: string | null;
  cluster_id: number | null;
  degree_centrality: number;
  top_techniques: string[];
}

export interface PapersResponse {
  total: number;
  page: number;
  per_page: number;
  results: PaperSummary[];
}

export interface SearchRequest {
  query: string;
  filters?: {
    conference?: string;
    year?: number;
    cluster?: number;
    technique?: string;
  };
  sort?: "relevance" | "citations" | "centrality" | "date";
  page?: number;
  per_page?: number;
}

export interface SearchResult {
  paper: PaperSummary;
  match_score: number;
  matched_in: string[];
}

export interface SearchResponse {
  query: string;
  total: number;
  page: number;
  per_page: number;
  results: SearchResult[];
}

export interface Author {
  id: string;
  full_name: string;
  position: number;
  affiliation: string | null;
  semantic_scholar_id: string | null;
  homepage: string | null;
}

export interface PaperTechnique {
  name: string;
  canonical_name: string | null;
  role: "introduces" | "uses" | "compares" | "critiques";
}

export interface PaperDataset {
  name: string;
  canonical_name: string | null;
  task: string | null;
  description: string | null;
}

export interface PaperCategory {
  name: string;
  canonical_name: string | null;
  confidence: number;
}

export interface PaperMethodology {
  name: string;
}

export interface PaperAnalysis {
  summary: string | null;
  advantages: string[];
  limitations: string[];
  future_work: string[];
  use_cases: string[];
  model: string | null;
}

export interface GraphMetrics {
  cluster_id: number | null;
  degree_centrality: number;
  betweenness_centrality: number;
  neighbors_count: number;
  total_edge_weight: number;
}

export interface PaperDetail {
  id: string;
  title: string;
  abstract: string | null;
  year: number;
  conference: string | null;
  edition_year: number | null;
  presentation_type: string | null;
  citation_count: number;
  influential_citation_count: number;
  is_open_access: boolean;
  pdf_url: string | null;
  openreview_id: string | null;
  semantic_scholar_id: string | null;
  arxiv_id: string | null;
  authors: Author[];
  techniques: PaperTechnique[];
  datasets: PaperDataset[];
  categories: PaperCategory[];
  methodologies: PaperMethodology[];
  analysis: PaperAnalysis | null;
  graph_metrics: GraphMetrics | null;
}

export interface RelatedPaperEntry {
  paper: PaperSummary;
  weight: number;
  shared_techniques: string[];
  shared_datasets: string[];
  shared_categories: string[];
  shared_methodologies: string[];
}

export interface RelatedPapersResponse {
  paper_id: string;
  title: string;
  graph_metrics: GraphMetrics | null;
  related: RelatedPaperEntry[];
}

export interface TechniqueItem {
  canonical_name: string;
  usage_count: number;
  connected_papers_count: number;
  top_cooccurring: string[];
  introduces_count: number;
  uses_count: number;
}

export interface TechniquesResponse {
  total: number;
  page: number;
  per_page: number;
  techniques: TechniqueItem[];
}
