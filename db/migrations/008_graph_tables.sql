-- Migration 008: knowledge graph tables
-- paper_relationships, entity_relationships, paper_graph_metrics, technique_graph_metrics
-- Apply (PostgreSQL): psql $DATABASE_URL -f db/migrations/008_graph_tables.sql
-- For SQLite dev: python -m db.migrate  (ORM creates all tables)

CREATE TABLE IF NOT EXISTS paper_relationships (
    id                   TEXT         PRIMARY KEY,
    source_paper_id      TEXT         NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    target_paper_id      TEXT         NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    shared_techniques    TEXT,                          -- JSON array
    shared_datasets      TEXT,                          -- JSON array
    shared_categories    TEXT,                          -- JSON array
    shared_methodologies TEXT,                          -- JSON array
    weight               REAL         NOT NULL DEFAULT 0,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (source_paper_id, target_paper_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_rel_source ON paper_relationships(source_paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_rel_target ON paper_relationships(target_paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_rel_weight ON paper_relationships(weight DESC);

CREATE TABLE IF NOT EXISTS entity_relationships (
    id                   TEXT         PRIMARY KEY,
    source_entity        TEXT         NOT NULL,
    target_entity        TEXT         NOT NULL,
    entity_type          TEXT         NOT NULL CHECK (entity_type IN ('technique','dataset','category','methodology')),
    co_occurrence_count  INTEGER      NOT NULL DEFAULT 1,
    weight               REAL         NOT NULL DEFAULT 1,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (source_entity, target_entity, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_entity_rel_source      ON entity_relationships(source_entity);
CREATE INDEX IF NOT EXISTS idx_entity_rel_target      ON entity_relationships(target_entity);
CREATE INDEX IF NOT EXISTS idx_entity_rel_type_weight ON entity_relationships(entity_type, weight DESC);

CREATE TABLE IF NOT EXISTS paper_graph_metrics (
    paper_id               TEXT        PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
    degree_centrality      REAL        NOT NULL DEFAULT 0,
    betweenness_centrality REAL        NOT NULL DEFAULT 0,
    cluster_id             INTEGER,
    neighbors_count        INTEGER     NOT NULL DEFAULT 0,
    total_edge_weight      REAL        NOT NULL DEFAULT 0,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_metrics_cluster ON paper_graph_metrics(cluster_id);
CREATE INDEX IF NOT EXISTS idx_paper_metrics_bc      ON paper_graph_metrics(betweenness_centrality DESC);

CREATE TABLE IF NOT EXISTS technique_graph_metrics (
    canonical_name         TEXT        PRIMARY KEY,
    usage_count            INTEGER     NOT NULL DEFAULT 0,
    connected_papers_count INTEGER     NOT NULL DEFAULT 0,
    top_cooccurring        TEXT,                        -- JSON array
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tech_metrics_usage ON technique_graph_metrics(usage_count DESC);
