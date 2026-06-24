-- Migration 006: Feature Mapper tables (Project-to-Research feature mapping, Phase 1)
--
-- SQLite: handled automatically by SQLAlchemy Base.metadata.create_all()
--         (see db/migrate.py — the FmProject/FmFeature/FmPaperMatch ORM models).
-- Postgres: run via  psql $DATABASE_URL -f db/migrations/006_feature_mapper.sql
--
-- Three tables:
--   fm_projects      — one row per analysed document
--   fm_features      — discrete features extracted from a project
--   fm_paper_matches — papers retrieved for each feature
--
-- NOTE: On Postgres the list-valued columns are TEXT (JSON-encoded) to match
-- the SQLite ORM storage convention used across this codebase (paper_analyses
-- stores JSON arrays as TEXT). This keeps a single serialization path.

CREATE TABLE IF NOT EXISTS fm_projects (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title             TEXT,
    input_text        TEXT NOT NULL,
    feature_count     INTEGER,
    total_duration_ms INTEGER,
    llm_model         TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fm_features (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES fm_projects(id) ON DELETE CASCADE,
    position            SMALLINT NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT NOT NULL,
    source_section      TEXT,
    source_text         TEXT NOT NULL,
    feature_type        TEXT NOT NULL DEFAULT 'other',
    matched_techniques  TEXT,   -- JSON array of names
    matched_categories  TEXT,   -- JSON array of names
    unrecognized_terms  TEXT,   -- JSON array of terms
    coverage_score      REAL,
    coverage_tier       TEXT,   -- strong | moderate | weak | novel
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fm_features_project ON fm_features (project_id, position);

CREATE TABLE IF NOT EXISTS fm_paper_matches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id          UUID NOT NULL REFERENCES fm_features(id) ON DELETE CASCADE,
    paper_id            UUID NOT NULL,
    rank                SMALLINT NOT NULL,
    semantic_score      REAL,
    technique_score     REAL,
    category_score      REAL,
    rrf_score           REAL NOT NULL,
    matched_techniques  TEXT,   -- JSON array
    matched_categories  TEXT,   -- JSON array
    -- Phase 2B — relevance explanation
    relevance_explanation TEXT,         -- 2-4 sentence paragraph
    similarity_points     TEXT,         -- JSON array of bullets
    difference_points     TEXT,         -- JSON array of bullets
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (feature_id, paper_id)
);

CREATE INDEX IF NOT EXISTS idx_fm_matches_feature ON fm_paper_matches (feature_id, rank);

-- Phase 2C — recommendations (one row per recommendation per feature)
CREATE TABLE IF NOT EXISTS fm_recommendations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id           UUID NOT NULL REFERENCES fm_features(id) ON DELETE CASCADE,
    rec_type             TEXT NOT NULL,   -- missing_technique | evaluation_suggestion
    rank                 SMALLINT NOT NULL,
    title                TEXT NOT NULL,
    body                 TEXT NOT NULL,
    supporting_paper_ids TEXT,            -- JSON array of paper_ids
    priority_score       REAL,
    evidence_count       SMALLINT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fm_recs_feature ON fm_recommendations (feature_id, rank);

-- Phase 3 — project-level research report (one per project)
CREATE TABLE IF NOT EXISTS fm_reports (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL UNIQUE REFERENCES fm_projects(id) ON DELETE CASCADE,
    markdown_content  TEXT NOT NULL,
    sections          TEXT,            -- JSON: {section_name: content}
    llm_model         TEXT,
    generation_ms     INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
