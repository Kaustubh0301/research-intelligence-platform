"""
Graph analytics: centrality, clustering, and technique metrics.

Reads from paper_relationships and entity_relationships.
Writes to paper_graph_metrics and technique_graph_metrics.

Uses NetworkX for graph algorithms.
Clustering: greedy_modularity_communities (fast, works well for n~100).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

import networkx as nx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import (
    EntityRelationship,
    Paper,
    PaperGraphMetric,
    PaperRelationship,
    PaperTechnique,
    TechniqueGraphMetric,
)

log = logging.getLogger(__name__)


@dataclass
class AnalyticsStats:
    papers_in_graph:       int = 0
    isolated_papers:       int = 0
    total_edges:           int = 0
    clusters_found:        int = 0
    largest_cluster_size:  int = 0
    techniques_computed:   int = 0


# ── Build NetworkX graph ───────────────────────────────────────────────────────

def _build_nx_graph(session: Session) -> nx.Graph:
    """Load paper_relationships into a weighted NetworkX graph."""
    G = nx.Graph()

    # Add all paper nodes (including isolated ones)
    for pid in session.scalars(select(Paper.id)).all():
        G.add_node(pid)

    # Add weighted edges from paper_relationships
    for row in session.execute(
        select(
            PaperRelationship.source_paper_id,
            PaperRelationship.target_paper_id,
            PaperRelationship.weight,
        )
    ).all():
        G.add_edge(row.source_paper_id, row.target_paper_id, weight=row.weight)

    return G


# ── Centrality computation ─────────────────────────────────────────────────────

def _compute_centrality(G: nx.Graph) -> tuple[dict[str, float], dict[str, float]]:
    """
    Return (degree_centrality, betweenness_centrality) for all nodes.
    Betweenness is computed on the largest connected component if the graph
    is disconnected (avoids zero-division on isolated nodes).
    """
    degree_c     = nx.degree_centrality(G)
    # Betweenness on full graph (handles disconnected: paths don't cross components)
    betweenness_c = nx.betweenness_centrality(G, weight="weight", normalized=True)
    return degree_c, betweenness_c


# ── Community detection ───────────────────────────────────────────────────────

def _detect_communities(G: nx.Graph) -> dict[str, int]:
    """
    Assign a cluster_id to every paper node.
    Uses greedy_modularity_communities on the connected subgraph;
    isolated nodes each get their own singleton cluster.

    Returns {paper_id: cluster_id}.
    """
    clusters: dict[str, int] = {}
    cluster_id = 0

    # Separate connected vs isolated
    connected_nodes = [n for n in G.nodes() if G.degree(n) > 0]
    isolated_nodes  = [n for n in G.nodes() if G.degree(n) == 0]

    if connected_nodes:
        subgraph   = G.subgraph(connected_nodes)
        communities = nx.community.greedy_modularity_communities(
            subgraph, weight="weight"
        )
        for community in sorted(communities, key=len, reverse=True):
            for node in sorted(community):
                clusters[node] = cluster_id
            cluster_id += 1

    # Isolated nodes: each gets its own cluster
    for node in sorted(isolated_nodes):
        clusters[node] = cluster_id
        cluster_id += 1

    return clusters


# ── Write paper_graph_metrics ─────────────────────────────────────────────────

def _write_paper_metrics(
    session: Session,
    G: nx.Graph,
    degree_c: dict[str, float],
    betweenness_c: dict[str, float],
    clusters: dict[str, int],
) -> AnalyticsStats:
    """Truncate and repopulate paper_graph_metrics."""
    session.execute(delete(PaperGraphMetric))
    session.flush()

    stats = AnalyticsStats(
        papers_in_graph = G.number_of_nodes(),
        total_edges     = G.number_of_edges(),
        clusters_found  = len(set(clusters.values())),
    )

    cluster_sizes: dict[int, int] = defaultdict(int)

    for pid in G.nodes():
        neighbors = list(G.neighbors(pid))
        total_w   = sum(G[pid][nb]["weight"] for nb in neighbors)

        session.add(PaperGraphMetric(
            paper_id               = pid,
            degree_centrality      = degree_c.get(pid, 0.0),
            betweenness_centrality = betweenness_c.get(pid, 0.0),
            cluster_id             = clusters.get(pid),
            neighbors_count        = len(neighbors),
            total_edge_weight      = total_w,
        ))
        cluster_sizes[clusters.get(pid, -1)] += 1

    session.flush()

    stats.isolated_papers    = sum(1 for pid in G.nodes() if G.degree(pid) == 0)
    stats.largest_cluster_size = max(cluster_sizes.values(), default=0)

    return stats


# ── Technique graph metrics ───────────────────────────────────────────────────

def _write_technique_metrics(session: Session, stats: AnalyticsStats) -> None:
    """
    Compute and write technique_graph_metrics.

    usage_count:            distinct papers using this canonical technique.
    connected_papers_count: papers reachable through the paper graph from any
                            paper that uses this technique (union of neighbors).
    top_cooccurring:        top-5 co-occurring canonical techniques by co_occurrence_count.
    """
    session.execute(delete(TechniqueGraphMetric))
    session.flush()

    # usage_count per canonical technique
    rows = session.execute(
        select(
            PaperTechnique.canonical_name,
            PaperTechnique.paper_id,
        )
        .where(PaperTechnique.canonical_name.isnot(None))
    ).all()

    # Build: canonical → {paper_ids}
    tech_papers: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        tech_papers[r.canonical_name].add(r.paper_id)

    # Load paper neighbor map from paper_relationships
    neighbor_map: dict[str, set[str]] = defaultdict(set)
    for rel in session.execute(
        select(PaperRelationship.source_paper_id, PaperRelationship.target_paper_id)
    ).all():
        neighbor_map[rel.source_paper_id].add(rel.target_paper_id)
        neighbor_map[rel.target_paper_id].add(rel.source_paper_id)

    # Load co-occurrence map for techniques
    cooccur_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for rel in session.execute(
        select(
            EntityRelationship.source_entity,
            EntityRelationship.target_entity,
            EntityRelationship.co_occurrence_count,
        )
        .where(EntityRelationship.entity_type == "technique")
    ).all():
        cooccur_map[rel.source_entity][rel.target_entity] = rel.co_occurrence_count
        cooccur_map[rel.target_entity][rel.source_entity] = rel.co_occurrence_count

    count = 0
    for canonical, using_papers in tech_papers.items():
        # Papers reachable through the graph from any paper using this technique
        reachable = set(using_papers)
        for pid in using_papers:
            reachable |= neighbor_map.get(pid, set())

        # Top co-occurring techniques
        cooccur = cooccur_map.get(canonical, {})
        top_cooccurring = sorted(
            [{"name": k, "count": v} for k, v in cooccur.items()],
            key=lambda x: -x["count"],
        )[:5]

        session.add(TechniqueGraphMetric(
            canonical_name          = canonical,
            usage_count             = len(using_papers),
            connected_papers_count  = len(reachable),
            top_cooccurring         = json.dumps(top_cooccurring),
        ))
        count += 1

    session.flush()
    stats.techniques_computed = count


# ── Public entry point ─────────────────────────────────────────────────────────

def run(session: Session) -> AnalyticsStats:
    """
    Compute all graph metrics.  Must be called after graph.builder.build().
    Truncates and repopulates paper_graph_metrics and technique_graph_metrics.
    """
    log.info("Graph analytics: building NetworkX graph")
    G = _build_nx_graph(session)
    log.info(
        "Graph analytics: %d nodes, %d edges",
        G.number_of_nodes(), G.number_of_edges()
    )

    log.info("Graph analytics: computing centrality")
    degree_c, betweenness_c = _compute_centrality(G)

    log.info("Graph analytics: detecting communities")
    clusters = _detect_communities(G)
    n_clusters = len(set(clusters.values()))
    log.info("Graph analytics: %d communities found", n_clusters)

    log.info("Graph analytics: writing paper_graph_metrics")
    stats = _write_paper_metrics(session, G, degree_c, betweenness_c, clusters)

    log.info("Graph analytics: writing technique_graph_metrics")
    _write_technique_metrics(session, stats)

    session.commit()
    log.info(
        "Graph analytics: done — %d papers, %d edges, %d clusters, %d techniques",
        stats.papers_in_graph, stats.total_edges, stats.clusters_found, stats.techniques_computed,
    )
    return stats
