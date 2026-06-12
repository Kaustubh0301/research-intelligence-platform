-- Migration 010: FTS5 virtual tables for full-text search.
--
-- Creates papers_fts (title + abstract) and entities_fts (techniques + categories).
-- Datasets are excluded in Phase 1.
--
-- These tables hold derived data only; they are always re-populatable from
-- the source tables via:  python rebuild_fts.py
--
-- This migration only creates the tables.  Backfill is NOT performed here.
-- Run rebuild_fts.py after applying this migration.

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    paper_id,
    title,
    abstract,
    tokenize = 'porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    paper_id,
    entity_type,   -- 'technique' | 'category'  (Phase 1; 'dataset' added in Phase 2)
    name,
    tokenize = 'unicode61'
);
