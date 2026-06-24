-- Migration 006: add notebooklm_id to notebooks
-- The notebooklm_id is the internal UUID returned by `nlm notebook create --json`
-- and required by all subsequent `nlm source add` / `nlm notebook query` calls.
-- It is distinct from notebooklm_url (the browser URL).
--
-- Apply with: psql $DATABASE_URL -f db/migrations/006_add_notebooklm_id.sql
-- For SQLite dev: python -m db.migrate (ORM creates the column automatically)

ALTER TABLE notebooks ADD COLUMN IF NOT EXISTS notebooklm_id VARCHAR(64);
