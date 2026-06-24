"""
Pick 30 unprocessed papers for validation batch.
Selection: highest citation_count among papers with no entity data and no PDF yet.
Prints paper IDs and titles.
"""
import sqlite3
conn = sqlite3.connect("research_platform.db")
rows = conn.execute("""
    SELECT p.id, p.title, p.citation_count, p.pdf_url, ce.conference_id
    FROM papers p
    JOIN conference_editions ce ON ce.id = p.conference_edition_id
    WHERE NOT EXISTS (SELECT 1 FROM paper_techniques pt WHERE pt.paper_id = p.id)
    AND NOT EXISTS (SELECT 1 FROM paper_categories  pc WHERE pc.paper_id = p.id)
    AND NOT EXISTS (SELECT 1 FROM notebook_papers   np WHERE np.paper_id = p.id)
    AND p.pdf_url IS NOT NULL AND p.pdf_url != ''
    ORDER BY p.citation_count DESC NULLS LAST
    LIMIT 30
""").fetchall()
print(f"Selected {len(rows)} papers for validation batch")
print()
for i, r in enumerate(rows, 1):
    print(f"  {i:2d}. [{r[4][:8]}] cit={r[2] or 0:4d}  {r[1][:70]}")
    print(f"       id={r[0]}")
conn.close()
