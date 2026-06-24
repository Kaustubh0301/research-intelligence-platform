"""Quick test: keyword-only vs hybrid retrieval for a paraphrase query."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(str(ROOT / ".env"), override=True)

QUERY = "small model learns from big model"

# ── Keyword-only ──────────────────────────────────────────────────────────────
os.environ["SEMANTIC_SEARCH"] = "false"

from db.session import get_session
from search.retrieval import retrieve_papers_for_query

print(f"Query: {QUERY!r}\n")
print("KEYWORD-ONLY:")
with get_session() as s:
    kw_results = retrieve_papers_for_query(QUERY, s)
    for r in kw_results[:5]:
        print(f"  [{r['match_score']:6.1f}] {r['title'][:72]}")

# ── Hybrid ────────────────────────────────────────────────────────────────────
os.environ["SEMANTIC_SEARCH"] = "true"

from search.embeddings import get_index
get_index().load()

print("\nSEMANTIC RAW SCORES (top 10):")
idx = get_index()
sem = idx.search(QUERY, k=10)
print(f"  Raw hit count: {len(sem)}")
if sem:
    from db.session import get_session as _gs
    from search.metadata import fetch_paper_metadata_batch
    from sqlalchemy import text as _text
    top_ids = sorted(sem.keys(), key=lambda x: -sem[x])[:10]
    print(f"  Sample index ID: {top_ids[0]}")
    with _gs() as s2:
        meta = fetch_paper_metadata_batch(s2, top_ids)
        sample = s2.execute(_text("SELECT id FROM papers LIMIT 1")).fetchone()
        print(f"  Sample DB ID:    {sample[0] if sample else 'N/A'}")
    found_in_db = sum(1 for pid in top_ids if pid in meta)
    print(f"  IDs found in DB: {found_in_db}/{len(top_ids)}")
    for pid, score in sorted(sem.items(), key=lambda x: -x[1])[:5]:
        title = meta.get(pid, {}).get("title", "NOT IN DB")[:60]
        print(f"  [{score:.3f}] {pid[:20]}… | {title}")
else:
    print("  (none above 0.30 threshold)")

print("\nHYBRID (keyword + semantic):")
with get_session() as s:
    hy_results = retrieve_papers_for_query(QUERY, s)
    for r in hy_results[:5]:
        tags = r.get("matched_in", [])
        star = "★" if "semantic" in tags and len(tags) == 1 else " "
        print(f"  {star}[{r['match_score']:6.1f}] {tags} | {r['title'][:60]}")

print("\n★ = entered via semantic search only")
