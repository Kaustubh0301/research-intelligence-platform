/**
 * Feature flags — UI visibility toggles.
 *
 * These flags hide UI surfaces only. All backend APIs, DB tables,
 * graph pipelines, and React components remain fully intact.
 *
 * To re-enable a feature: set its flag to `true` and restart the dev server.
 *
 * FEATURES.GRAPH
 *   Controls: Graph nav link, /graph page, "Graph Edges" + "Clusters" stat
 *   cards on the dashboard, the Cluster Overview dashboard widget, and the
 *   graph-metrics block (cluster badge, neighbours, centrality) inside the
 *   paper detail MetricsCard.
 *
 * FEATURES.RELATED_PAPERS
 *   Controls: the Related Papers section on paper detail pages (including the
 *   API call to /papers/{id}/related).
 */
export const FEATURES = {
  GRAPH:          false,
  RELATED_PAPERS: true,
} as const;
