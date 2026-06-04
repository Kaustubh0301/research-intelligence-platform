-- Migration 003: PDF pipeline tables
-- Run via: psql $DATABASE_URL -f db/migrations/003_pdf_pipeline_tables.sql
-- SQLite: handled automatically by SQLAlchemy Base.metadata.create_all()

-- New columns on papers
ALTER TABLE papers ADD COLUMN IF NOT EXISTS pdf_local_path   TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS pdf_word_count   INTEGER;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS pdf_extracted_at TIMESTAMPTZ;

-- Section text extracted from the PDF
CREATE TABLE IF NOT EXISTS paper_sections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id          UUID NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,

    abstract          TEXT,
    introduction      TEXT,
    related_work      TEXT,
    methodology       TEXT,
    experiments       TEXT,
    results           TEXT,
    discussion        TEXT,
    conclusion        TEXT,
    limitations       TEXT,
    future_work       TEXT,
    full_text         TEXT,

    sections_found    TEXT,          -- JSON array of detected section keys
    word_count        INT,
    segmenter_version TEXT,
    segmented_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Datasets mentioned in experiments sections
CREATE TABLE IF NOT EXISTS paper_datasets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id    UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    task        TEXT,
    source      TEXT DEFAULT 'auto',
    UNIQUE (paper_id, name)
);

-- LLM-generated structured analysis (extends summaries concept)
CREATE TABLE IF NOT EXISTS paper_analyses (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id       UUID NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,

    summary        TEXT,
    advantages     TEXT,            -- JSON array
    limitations    TEXT,            -- JSON array
    future_work    TEXT,            -- JSON array
    use_cases      TEXT,            -- JSON array

    model          TEXT,
    input_tokens   INT,
    output_tokens  INT,
    cost_usd       REAL,
    processing_ms  INT,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Per-paper per-stage error log (never deletes, append-only)
CREATE TABLE IF NOT EXISTS pipeline_errors (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id    UUID REFERENCES papers(id),
    stage       TEXT NOT NULL,      -- 'download' | 'extract' | 'segment' | 'analyse'
    error_type  TEXT NOT NULL,      -- 'http_404' | 'timeout' | 'json_invalid' | …
    error_msg   TEXT,
    retryable   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
