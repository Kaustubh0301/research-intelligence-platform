-- Migration 005: NotebookLM integration tables
-- Apply with: psql $DATABASE_URL -f db/migrations/005_notebooks.sql
-- For SQLite dev: run_migrations() in db/migrate.py handles table creation via ORM.

-- One row per NotebookLM notebook (one per topic × instance)
CREATE TABLE IF NOT EXISTS notebooks (
    id              TEXT        PRIMARY KEY,
    topic_slug      TEXT        NOT NULL,
    topic_name      TEXT        NOT NULL,
    instance_number SMALLINT    NOT NULL DEFAULT 1,
    notebooklm_url  TEXT,
    source_count    SMALLINT    NOT NULL DEFAULT 0,
    max_sources     SMALLINT    NOT NULL DEFAULT 45,
    status          TEXT        NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','full','archived')),
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (topic_slug, instance_number)
);

-- Many-to-many: which papers are assigned to which notebook, with upload state
CREATE TABLE IF NOT EXISTS notebook_papers (
    notebook_id             TEXT        NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    paper_id                TEXT        NOT NULL REFERENCES papers(id)    ON DELETE CASCADE,
    assigned_by             TEXT        NOT NULL DEFAULT 'keyword',   -- keyword|manual|notebooklm
    assignment_confidence   TEXT        NOT NULL DEFAULT 'medium',    -- high|medium|low
    source_status           TEXT        NOT NULL DEFAULT 'pending'
                                CHECK (source_status IN ('pending','uploaded','abstract_only','error','removed')),
    upload_attempted_at     TIMESTAMPTZ,
    upload_completed_at     TIMESTAMPTZ,
    PRIMARY KEY (notebook_id, paper_id)
);

-- Notebook-level synthesis outputs (query responses from NotebookLM)
CREATE TABLE IF NOT EXISTS notebook_syntheses (
    id              TEXT        PRIMARY KEY,
    notebook_id     TEXT        NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    synthesis_type  TEXT        NOT NULL
                        CHECK (synthesis_type IN ('faq','study_guide','briefing','overview','query_response')),
    query_prompt    TEXT,
    content         TEXT        NOT NULL,
    word_count      INT,
    normalized      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (notebook_id, synthesis_type, query_prompt)
);

-- Per-paper extracts parsed out of synthesis responses
-- Intermediate table; normalised into paper_analyses, paper_categories, etc.
CREATE TABLE IF NOT EXISTS notebook_paper_extracts (
    id              TEXT        PRIMARY KEY,
    notebook_id     TEXT        NOT NULL REFERENCES notebooks(id)          ON DELETE CASCADE,
    synthesis_id    TEXT        NOT NULL REFERENCES notebook_syntheses(id) ON DELETE CASCADE,
    paper_id        TEXT        NOT NULL REFERENCES papers(id)             ON DELETE CASCADE,
    extract_type    TEXT        NOT NULL
                        CHECK (extract_type IN (
                            'summary','techniques','methodologies',
                            'limitations','datasets','categories','future_work'
                        )),
    content         TEXT        NOT NULL,
    confidence      TEXT        NOT NULL DEFAULT 'medium',
    normalized      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common access patterns
CREATE INDEX IF NOT EXISTS idx_notebook_papers_paper_id    ON notebook_papers (paper_id);
CREATE INDEX IF NOT EXISTS idx_notebook_papers_status      ON notebook_papers (source_status);
CREATE INDEX IF NOT EXISTS idx_notebook_syntheses_notebook ON notebook_syntheses (notebook_id);
CREATE INDEX IF NOT EXISTS idx_npe_paper_id                ON notebook_paper_extracts (paper_id);
CREATE INDEX IF NOT EXISTS idx_npe_notebook_id             ON notebook_paper_extracts (notebook_id);
CREATE INDEX IF NOT EXISTS idx_npe_normalized              ON notebook_paper_extracts (normalized);
