-- Migration 007: add canonical_name to analysis tag tables
-- canonical_name stores the normalized form; name is never modified.
-- Apply (PostgreSQL): psql $DATABASE_URL -f db/migrations/007_canonical_name.sql
-- For SQLite dev: python -m db.migrate (or run ALTER TABLE directly)

ALTER TABLE paper_techniques    ADD COLUMN IF NOT EXISTS canonical_name TEXT;
ALTER TABLE paper_datasets      ADD COLUMN IF NOT EXISTS canonical_name TEXT;
ALTER TABLE paper_categories    ADD COLUMN IF NOT EXISTS canonical_name TEXT;
