"""
search/
───────
FTS5-backed retrieval package.

Public surface:
    from search import retrieve_papers_for_query
    from search import fts_score
    from search.sync import sync_papers, sync_entities, rebuild_all
    from search.fts import tables_exist, tables_healthy
"""

from search.retrieval import fts_score, retrieve_papers_for_query
from search.sync import rebuild_all, sync_entities, sync_papers

__all__ = [
    "retrieve_papers_for_query",
    "fts_score",
    "sync_papers",
    "sync_entities",
    "rebuild_all",
]
