"""
tests/test_fts.py
─────────────────
Unit tests for the FTS5 search module.

Runs against an in-memory SQLite database with the FTS5 virtual tables
created inline (no migration file needed).  Each test function gets a
fresh session via the `session` fixture.

Run with:
    pytest tests/test_fts.py -v
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from search.fts import (
    query_entities_fts,
    query_papers_abstract_only,
    query_papers_fts,
    query_papers_title_only,
    tables_exist,
    tables_healthy,
)
from search.sync import (
    SQLITE_IN_LIMIT,
    _chunks,
    rebuild_all,
    sync_entities,
    sync_papers,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    citation_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS paper_techniques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT,
    name TEXT,
    canonical_name TEXT,
    role TEXT
);

CREATE TABLE IF NOT EXISTS paper_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT,
    name TEXT,
    canonical_name TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    paper_id,
    title,
    abstract,
    tokenize = 'porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    paper_id,
    entity_type,
    name,
    tokenize = 'unicode61'
);
"""

_SEED_PAPERS = [
    ("p1", "Attention Is All You Need",       "Transformer architecture using self-attention mechanism.", 10000),
    ("p2", "BERT: Pre-training of Deep Bidirectional Transformers", "Language model pre-training.", 8000),
    ("p3", "Deep Residual Learning for Image Recognition",  "ResNets use skip connections.", 9000),
    ("p4", "Generative Adversarial Networks",               "GAN training with generator and discriminator.", 7000),
    ("p5", "Adam: A Method for Stochastic Optimization",    "Adaptive learning rate optimizer.", 5000),
]

_SEED_TECHNIQUES = [
    ("p1", "Self-Attention",    "Self-Attention",    "introduces"),
    ("p2", "BERT",              "BERT",              "introduces"),
    ("p3", "Residual Networks", "Residual Networks", "introduces"),
    ("p4", "GAN",               "GAN",               "introduces"),
    ("p5", "Adam Optimizer",    "Adam Optimizer",    "introduces"),
]

_SEED_CATEGORIES = [
    ("p1", "Natural Language Processing", "Natural Language Processing", 0.95),
    ("p2", "Natural Language Processing", "Natural Language Processing", 0.98),
    ("p3", "Computer Vision",             "Computer Vision",             0.97),
    ("p4", "Generative Models",           "Generative Models",           0.93),
    ("p5", "Optimization",                "Optimization",                0.91),
]


def _make_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.begin() as conn:
        for stmt in _DDL.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    return engine


def _seed(session: Session) -> None:
    for pid, title, abstract, cites in _SEED_PAPERS:
        session.execute(
            text("INSERT INTO papers VALUES (:id, :title, :abstract, :cites)"),
            {"id": pid, "title": title, "abstract": abstract, "cites": cites},
        )
    for pid, name, canonical, role in _SEED_TECHNIQUES:
        session.execute(
            text("INSERT INTO paper_techniques(paper_id, name, canonical_name, role) VALUES (:p, :n, :c, :r)"),
            {"p": pid, "n": name, "c": canonical, "r": role},
        )
    for pid, name, canonical, conf in _SEED_CATEGORIES:
        session.execute(
            text("INSERT INTO paper_categories(paper_id, name, canonical_name, confidence) VALUES (:p, :n, :c, :cf)"),
            {"p": pid, "n": name, "c": canonical, "cf": conf},
        )
    session.commit()


@pytest.fixture()
def session():
    engine = _make_engine()
    with Session(bind=engine) as s:
        _seed(s)
        yield s


@pytest.fixture()
def populated_session(session):
    """Session with FTS tables fully populated via rebuild_all."""
    rebuild_all(session)
    session.commit()
    return session


# ── tests: search/sync.py ─────────────────────────────────────────────────────

def test_sqlite_in_limit_is_900():
    assert SQLITE_IN_LIMIT == 900


def test_chunks_splits_evenly():
    result = list(_chunks([1, 2, 3, 4, 5, 6], 2))
    assert result == [[1, 2], [3, 4], [5, 6]]


def test_chunks_handles_remainder():
    result = list(_chunks([1, 2, 3, 4, 5], 3))
    assert result == [[1, 2, 3], [4, 5]]


def test_chunks_empty_input():
    assert list(_chunks([], 3)) == []


def test_sync_papers_inserts_rows(session):
    n = sync_papers(session, ["p1", "p2"])
    session.commit()
    count = session.execute(text("SELECT COUNT(*) FROM papers_fts")).scalar()
    assert count == 2


def test_sync_papers_is_idempotent(session):
    sync_papers(session, ["p1"])
    session.commit()
    sync_papers(session, ["p1"])
    session.commit()
    count = session.execute(text("SELECT COUNT(*) FROM papers_fts WHERE paper_id = 'p1'")).scalar()
    assert count == 1


def test_sync_papers_empty_list_is_noop(session):
    n = sync_papers(session, [])
    assert n == 0


def test_sync_entities_inserts_technique_and_category(session):
    n = sync_entities(session, ["p1"])
    session.commit()
    count = session.execute(text("SELECT COUNT(*) FROM entities_fts WHERE paper_id = 'p1'")).scalar()
    assert count == 2   # 1 technique + 1 category


def test_sync_entities_empty_list_is_noop(session):
    n = sync_entities(session, [])
    assert n == 0


def test_rebuild_all_populates_both_tables(session):
    n_papers, n_entities = rebuild_all(session)
    session.commit()
    assert n_papers == 5
    assert n_entities == 10  # 5 techniques + 5 categories


def test_rebuild_all_is_idempotent(session):
    rebuild_all(session)
    session.commit()
    rebuild_all(session)
    session.commit()
    count = session.execute(text("SELECT COUNT(*) FROM papers_fts")).scalar()
    assert count == 5


# ── tests: search/fts.py ──────────────────────────────────────────────────────

def test_tables_exist_true(populated_session):
    assert tables_exist(populated_session) is True


def test_tables_exist_false(session):
    # Drop both FTS tables to simulate missing state.
    session.execute(text("DROP TABLE IF EXISTS papers_fts"))
    session.execute(text("DROP TABLE IF EXISTS entities_fts"))
    session.commit()
    assert tables_exist(session) is False


def test_tables_healthy_when_populated(populated_session):
    ok, msg = tables_healthy(populated_session)
    assert ok, f"Expected healthy, got: {msg}"


def test_tables_healthy_fails_when_unpopulated(session):
    ok, msg = tables_healthy(session)
    assert not ok
    assert "rebuild_fts.py" in msg


def test_query_papers_fts_returns_results(populated_session):
    hits = query_papers_fts(populated_session, "attention")
    ids = [h[0] for h in hits]
    assert "p1" in ids


def test_query_papers_fts_bm25_scores_positive(populated_session):
    hits = query_papers_fts(populated_session, "transformer")
    assert all(score > 0 for _, score in hits)


def test_query_papers_fts_empty_term_returns_empty(populated_session):
    assert query_papers_fts(populated_session, "") == []


def test_query_papers_title_only(populated_session):
    ids = query_papers_title_only(populated_session, "attention")
    assert "p1" in ids


def test_query_papers_abstract_only(populated_session):
    ids = query_papers_abstract_only(populated_session, "skip")
    assert "p3" in ids


def test_query_entities_fts_technique(populated_session):
    # Search by token — FTS5 unicode61 tokenizes on hyphens and spaces.
    hits = query_entities_fts(populated_session, "Residual")
    types = {h[1] for h in hits}
    assert "technique" in types


def test_query_entities_fts_category(populated_session):
    hits = query_entities_fts(populated_session, "Optimization")
    assert any(h[1] == "category" for h in hits)


def test_query_entities_fts_empty_term(populated_session):
    assert query_entities_fts(populated_session, "") == []
