"""
Inspect the local SQLite database populated by the ingestion pipeline.

Usage:
    python inspect_db.py                        # default: research_platform.db
    python inspect_db.py --db my_custom.db
"""

import argparse
import os
import sys

# Use SQLite by default; honour DATABASE_URL if already set
parser = argparse.ArgumentParser(description="Inspect the research platform database.")
parser.add_argument("--db", default="research_platform.db", help="SQLite file path (default: research_platform.db)")
args = parser.parse_args()

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = f"sqlite:///{args.db}"

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select
from db.models import Author, Conference, ConferenceEdition, Paper, Base
from db.session import engine, get_session

# Create tables if the file is brand-new (so the script never crashes on empty DB)
Base.metadata.create_all(engine)

DIVIDER = "─" * 52

with get_session() as session:
    n_conferences = session.scalar(select(func.count()).select_from(Conference))
    n_editions    = session.scalar(select(func.count()).select_from(ConferenceEdition))
    n_papers      = session.scalar(select(func.count()).select_from(Paper))
    n_authors     = session.scalar(select(func.count()).select_from(Author))

    # Materialise all needed fields inside the session to avoid DetachedInstanceError
    papers = [
        {"title": p.title, "presentation_type": p.presentation_type}
        for p in session.scalars(select(Paper).order_by(Paper.created_at).limit(10))
    ]
    authors = [
        {"full_name": a.full_name, "primary_affiliation": a.primary_affiliation}
        for a in session.scalars(select(Author).order_by(Author.created_at).limit(10))
    ]

print(DIVIDER)
print(" Database summary")
print(DIVIDER)
print(f"  Conferences        : {n_conferences}")
print(f"  Conference editions: {n_editions}")
print(f"  Papers             : {n_papers}")
print(f"  Authors            : {n_authors}")

print()
print(DIVIDER)
print(" First 10 paper titles")
print(DIVIDER)
if papers:
    for i, p in enumerate(papers, 1):
        print(f"  {i:>2}. [{p['presentation_type'] or 'n/a':10}]  {p['title'][:65]}")
else:
    print("  (no papers ingested yet)")

print()
print(DIVIDER)
print(" First 10 authors")
print(DIVIDER)
if authors:
    for i, a in enumerate(authors, 1):
        affil = f"  —  {a['primary_affiliation']}" if a["primary_affiliation"] else ""
        print(f"  {i:>2}. {a['full_name']}{affil}")
else:
    print("  (no authors ingested yet)")

print(DIVIDER)
