-- Research Intelligence Platform — PostgreSQL Schema
-- Target: 1,000–5,000 papers
-- Convention: snake_case, UUID primary keys, timestamptz for all datetimes

-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- fuzzy text search on titles/abstracts


-- ============================================================
-- CONFERENCES
-- Venues where papers are published.
-- ============================================================

CREATE TABLE conferences (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    short_name      TEXT NOT NULL UNIQUE,          -- e.g. 'NeurIPS', 'CVPR'
    full_name       TEXT NOT NULL,                 -- e.g. 'Neural Information Processing Systems'
    field           TEXT NOT NULL,                 -- 'ML', 'CV', 'NLP', 'AI'
    website         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Static seed rows are managed in db/seeds/conferences.sql


-- ============================================================
-- CONFERENCE EDITIONS
-- One row per year-conference pair (NeurIPS 2024, CVPR 2025 …)
-- Separates venue identity from a specific occurrence.
-- ============================================================

CREATE TABLE conference_editions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conference_id   UUID NOT NULL REFERENCES conferences(id) ON DELETE RESTRICT,
    year            SMALLINT NOT NULL,
    location        TEXT,                          -- 'Vancouver, BC, Canada'
    openreview_id   TEXT,                          -- 'NeurIPS.cc/2024/Conference'
    total_submitted INT,
    total_accepted  INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (conference_id, year)
);


-- ============================================================
-- AUTHORS
-- De-duplicated author entities.
-- One author may publish across many papers and conferences.
-- ============================================================

CREATE TABLE authors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name           TEXT NOT NULL,
    semantic_scholar_id TEXT UNIQUE,               -- S2 authorId
    openalex_id         TEXT UNIQUE,               -- OpenAlex author URL
    orcid               TEXT UNIQUE,
    homepage            TEXT,
    primary_affiliation TEXT,                      -- last known institution
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_authors_name_trgm ON authors USING GIN (full_name gin_trgm_ops);


-- ============================================================
-- PAPERS
-- Core entity. One row per published paper.
-- ============================================================

CREATE TABLE papers (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conference_edition_id   UUID REFERENCES conference_editions(id) ON DELETE SET NULL,

    -- Identifiers from upstream sources
    semantic_scholar_id     TEXT UNIQUE,
    openalex_id             TEXT UNIQUE,
    openreview_id           TEXT UNIQUE,           -- OpenReview note id
    arxiv_id                TEXT UNIQUE,           -- e.g. '2401.12345'
    doi                     TEXT UNIQUE,

    -- Core metadata
    title                   TEXT NOT NULL,
    abstract                TEXT,
    year                    SMALLINT NOT NULL,
    publication_date        DATE,
    presentation_type       TEXT CHECK (presentation_type IN
                                ('oral', 'spotlight', 'poster', 'workshop', 'demo', 'other')),

    -- Access
    pdf_url                 TEXT,
    is_open_access          BOOLEAN NOT NULL DEFAULT FALSE,

    -- Citation metrics (point-in-time snapshots; see paper_citation_snapshots for history)
    citation_count          INT NOT NULL DEFAULT 0,
    influential_citation_count INT NOT NULL DEFAULT 0,

    -- Freshness
    last_enriched_at        TIMESTAMPTZ,           -- last time citations/metadata were refreshed
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_papers_year              ON papers (year);
CREATE INDEX idx_papers_edition           ON papers (conference_edition_id);
CREATE INDEX idx_papers_citation_count    ON papers (citation_count DESC);
CREATE INDEX idx_papers_title_trgm        ON papers USING GIN (title gin_trgm_ops);
CREATE INDEX idx_papers_abstract_trgm     ON papers USING GIN (abstract gin_trgm_ops);


-- ============================================================
-- PAPER ↔ AUTHOR  (many-to-many)
-- Preserves author order on the paper.
-- ============================================================

CREATE TABLE paper_authors (
    paper_id        UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    author_id       UUID NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    position        SMALLINT NOT NULL,             -- 1 = first author
    is_corresponding BOOLEAN NOT NULL DEFAULT FALSE,
    affiliation     TEXT,                          -- affiliation at time of publication

    PRIMARY KEY (paper_id, author_id)
);

CREATE INDEX idx_paper_authors_author ON paper_authors (author_id);


-- ============================================================
-- CATEGORIES
-- Research area taxonomy. Supports a two-level hierarchy:
--   parent = NULL  →  top-level  (e.g. "Computer Vision")
--   parent = some id →  sub-area (e.g. "Object Detection")
-- ============================================================

CREATE TABLE categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,              -- 'computer-vision', 'object-detection'
    parent_id   UUID REFERENCES categories(id) ON DELETE SET NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- PAPER ↔ CATEGORY  (many-to-many)
-- A paper can belong to multiple categories.
-- source tracks whether the tag came from human curation or an LLM.
-- ============================================================

CREATE TABLE paper_categories (
    paper_id    UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    source      TEXT NOT NULL DEFAULT 'auto' CHECK (source IN ('auto', 'manual')),
    confidence  REAL CHECK (confidence BETWEEN 0 AND 1),  -- for auto-assigned tags

    PRIMARY KEY (paper_id, category_id)
);

CREATE INDEX idx_paper_categories_cat ON paper_categories (category_id);


-- ============================================================
-- TECHNIQUES
-- Fine-grained methodological building blocks.
-- Examples: "LoRA", "FlashAttention", "RLHF", "Contrastive Loss"
-- Reusable across papers and editions.
-- ============================================================

CREATE TABLE techniques (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,
    description TEXT,
    first_seen_year SMALLINT,                      -- year the technique was introduced
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- PAPER ↔ TECHNIQUE  (many-to-many)
-- role distinguishes whether a paper introduces, applies,
-- compares, or critiques a technique.
-- ============================================================

CREATE TABLE paper_techniques (
    paper_id    UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    technique_id UUID NOT NULL REFERENCES techniques(id) ON DELETE CASCADE,
    role        TEXT NOT NULL DEFAULT 'uses' CHECK (role IN ('introduces', 'uses', 'compares', 'critiques')),
    source      TEXT NOT NULL DEFAULT 'auto' CHECK (source IN ('auto', 'manual')),

    PRIMARY KEY (paper_id, technique_id)
);

CREATE INDEX idx_paper_techniques_tech ON paper_techniques (technique_id);


-- ============================================================
-- METHODOLOGIES
-- Higher-level research approaches.
-- Examples: "Supervised Learning", "Reinforcement Learning",
--           "Bayesian Inference", "Neural Architecture Search"
-- Coarser than techniques; finer than categories.
-- ============================================================

CREATE TABLE methodologies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- PAPER ↔ METHODOLOGY  (many-to-many)
-- ============================================================

CREATE TABLE paper_methodologies (
    paper_id        UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    methodology_id  UUID NOT NULL REFERENCES methodologies(id) ON DELETE CASCADE,
    source          TEXT NOT NULL DEFAULT 'auto' CHECK (source IN ('auto', 'manual')),

    PRIMARY KEY (paper_id, methodology_id)
);

CREATE INDEX idx_paper_methodologies_method ON paper_methodologies (methodology_id);


-- ============================================================
-- CITATIONS
-- Directed edge: citing_paper_id → cited_paper_id
-- Only stored when BOTH papers are in the local corpus.
-- For external citation counts, see papers.citation_count.
-- ============================================================

CREATE TABLE citations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citing_paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    cited_paper_id  UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    context         TEXT,                          -- sentence(s) around the citation (optional)
    is_influential  BOOLEAN NOT NULL DEFAULT FALSE,-- from Semantic Scholar
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (citing_paper_id, cited_paper_id),
    CONSTRAINT no_self_citation CHECK (citing_paper_id <> cited_paper_id)
);

CREATE INDEX idx_citations_cited   ON citations (cited_paper_id);
CREATE INDEX idx_citations_citing  ON citations (citing_paper_id);


-- ============================================================
-- PAPER CITATION SNAPSHOTS
-- Time-series of citation counts for trend analysis.
-- Insert one row per paper per refresh cycle (e.g. monthly).
-- ============================================================

CREATE TABLE paper_citation_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id        UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    snapshot_date   DATE NOT NULL,
    citation_count  INT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'semantic_scholar',

    UNIQUE (paper_id, snapshot_date, source)
);

CREATE INDEX idx_snapshots_paper ON paper_citation_snapshots (paper_id, snapshot_date DESC);


-- ============================================================
-- SUMMARIES
-- AI-generated or human-written summaries of papers.
-- Multiple summaries per paper are allowed (different types/lengths).
-- ============================================================

CREATE TABLE summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id        UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    summary_type    TEXT NOT NULL CHECK (summary_type IN
                        ('tldr', 'technical', 'lay', 'contribution', 'limitations')),
    content         TEXT NOT NULL,
    model           TEXT,                          -- 'claude-sonnet-4-6', 'gpt-4o', 'human', …
    word_count      SMALLINT GENERATED ALWAYS AS
                        (array_length(string_to_array(trim(content), ' '), 1)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (paper_id, summary_type)
);

CREATE INDEX idx_summaries_paper ON summaries (paper_id);


-- ============================================================
-- UPDATED_AT TRIGGER
-- Automatically bumps papers.updated_at on any row change.
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_papers_updated_at
BEFORE UPDATE ON papers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
