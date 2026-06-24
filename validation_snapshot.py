"""Snapshot DB state for before/after comparison during validation batch."""
import sqlite3, json, sys

conn = sqlite3.connect("research_platform.db")

def snapshot():
    return {
        "papers_total":        conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
        "papers_with_pdf":     conn.execute("SELECT COUNT(*) FROM papers WHERE pdf_local_path IS NOT NULL").fetchone()[0],
        "paper_sections":      conn.execute("SELECT COUNT(*) FROM paper_sections").fetchone()[0],
        "notebook_papers":     conn.execute("SELECT COUNT(*) FROM notebook_papers").fetchone()[0],
        "notebook_papers_uploaded": conn.execute(
            "SELECT COUNT(*) FROM notebook_papers WHERE source_status IN ('uploaded','abstract_only')"
        ).fetchone()[0],
        "notebook_syntheses":  conn.execute("SELECT COUNT(*) FROM notebook_syntheses").fetchone()[0],
        "paper_techniques":    conn.execute("SELECT COUNT(*) FROM paper_techniques").fetchone()[0],
        "paper_categories":    conn.execute("SELECT COUNT(*) FROM paper_categories").fetchone()[0],
        "paper_methodologies": conn.execute("SELECT COUNT(*) FROM paper_methodologies").fetchone()[0],
        "papers_with_entities": conn.execute("""
            SELECT COUNT(DISTINCT paper_id) FROM paper_techniques
        """).fetchone()[0],
        "entities_fts_rows":   conn.execute("SELECT COUNT(*) FROM entities_fts").fetchone()[0],
    }

if len(sys.argv) > 1 and sys.argv[1] == "diff":
    before = json.loads(sys.argv[2])
    after = snapshot()
    print("\n=== VALIDATION BATCH DELTA ===")
    print(f"  {'metric':35s}  before  after   delta")
    print(f"  {'-'*60}")
    for k in after:
        b, a = before.get(k, 0), after[k]
        delta = a - b
        flag = "  +" + str(delta) if delta > 0 else ("  " + str(delta) if delta < 0 else "")
        print(f"  {k:35s}  {b:6d}  {a:6d}{flag}")
else:
    s = snapshot()
    print(json.dumps(s, indent=2))

conn.close()
