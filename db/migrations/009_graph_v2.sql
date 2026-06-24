-- Migration 009: graph v2 — per-edge score diagnostics
-- Adds technique_score, dataset_score, category_score to paper_relationships.
-- weight column retains the final combined weight (unchanged meaning).
--
-- SQLite: each ADD COLUMN must be a separate statement.
-- PostgreSQL: can combine into one ALTER TABLE.

ALTER TABLE paper_relationships ADD COLUMN technique_score REAL;
ALTER TABLE paper_relationships ADD COLUMN dataset_score   REAL;
ALTER TABLE paper_relationships ADD COLUMN category_score  REAL;
