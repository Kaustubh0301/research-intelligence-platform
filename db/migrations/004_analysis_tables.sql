-- Migration 004: paper_categories, paper_techniques, paper_methodologies
-- Compatible with PostgreSQL; SQLite handled via db/migrate.py

CREATE TABLE IF NOT EXISTS paper_categories (
    id          TEXT        PRIMARY KEY,
    paper_id    TEXT        NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    confidence  REAL        NOT NULL DEFAULT 1.0,
    source      TEXT        NOT NULL DEFAULT 'auto',
    UNIQUE (paper_id, name)
);

CREATE TABLE IF NOT EXISTS paper_techniques (
    id          TEXT        PRIMARY KEY,
    paper_id    TEXT        NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    role        VARCHAR(20) NOT NULL DEFAULT 'uses'
                    CHECK (role IN ('introduces','uses','compares','critiques')),
    source      TEXT        NOT NULL DEFAULT 'auto',
    UNIQUE (paper_id, name)
);

CREATE TABLE IF NOT EXISTS paper_methodologies (
    id          TEXT        PRIMARY KEY,
    paper_id    TEXT        NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    source      TEXT        NOT NULL DEFAULT 'auto',
    UNIQUE (paper_id, name)
);

CREATE INDEX IF NOT EXISTS idx_paper_categories_paper  ON paper_categories  (paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_categories_name   ON paper_categories  (name);
CREATE INDEX IF NOT EXISTS idx_paper_techniques_paper  ON paper_techniques  (paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_techniques_name   ON paper_techniques  (name);
CREATE INDEX IF NOT EXISTS idx_paper_methodologies_paper ON paper_methodologies (paper_id);
