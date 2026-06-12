import sqlite3
conn = sqlite3.connect("research_platform.db")

VALIDATION_IDS = [
    "25c5fe6da1f947b7b511ffb23f2a5a04","efdef973e16448e8a290ebd1dad2fbeb",
    "9b2d4d4fcc974357a26b0b82a89bd876","fae4a819676f4b178b299dc1a925f262",
    "69801988f0e14ff39db1f536c39a59f9","89b7edc72fde49219e061f7754060399",
    "5a17eed4e1b2479dbdfb7c19537154fa","9e4aec9d1e6b4f4786e2016a5074fed5",
    "9ca6e4fab8854babbffe449f85a978c0","c5b22948e30646449e0dedac27c2f048",
    "230b8f9c4b724e639152dfac7f66f71e","79fe029b736c4b1a8e15416b3f6c4916",
    "76460e07687d44c3b7d63f7ff6c744fe","fb6008401ffd4dcb8c5974ec3b343e65",
    "2801f99bf2244b92ac11918649fdd759","e927487c1a4b420c925ea5079167133f",
    "62dee7f0c7484f7f8103fd4b388e29a7","842ea9f3288845d3a82e74477337a126",
    "5a085e3416074feea79723651b892c40","14e76e1ef57b492e9147a8795e78f230",
    "5a63b19cda5c4382ba2306a6dadf4c9d","b773dc8c7051452f868a53c47b576571",
    "781cafb418ce4c8e9b4b41636c4ab343","b7220693f9bc4a0182cddf5f625d0298",
    "0040bbe0dc2b4733b2a36eb321fcfcde","81cdc0d6ef6c44ec8d88572a39d7e666",
    "733cb5cc64ad47e9a1beb91b2b6440f1","8697cb702218433783d3e4f5d76507ab",
    "569f464905614e2b94ff19de02e40dd2","d5d7b1de1c0346a3b91d2b929591cf4f",
]
ph = ','.join(['?']*len(VALIDATION_IDS))

# 5 richest samples by technique count
sample_ids = [r[0] for r in conn.execute(
    "SELECT pt.paper_id, COUNT(*) n FROM paper_techniques pt "
    "WHERE pt.paper_id IN (" + ph + ") AND pt.source='notebooklm' "
    "GROUP BY pt.paper_id ORDER BY n DESC LIMIT 5",
    VALIDATION_IDS
).fetchall()]

print("=== 5 SAMPLE PAPERS ===\n")
for pid in sample_ids:
    title = conn.execute("SELECT title FROM papers WHERE id=?", (pid,)).fetchone()[0]
    techs = [r[0] for r in conn.execute(
        "SELECT name FROM paper_techniques WHERE paper_id=? AND source='notebooklm'", (pid,))]
    cats  = [r[0] for r in conn.execute(
        "SELECT name FROM paper_categories WHERE paper_id=? AND source='notebooklm'", (pid,))]
    meths = [r[0] for r in conn.execute(
        "SELECT name FROM paper_methodologies WHERE paper_id=? AND source='notebooklm'", (pid,))]
    print("PAPER:", title)
    print("  techniques    (" + str(len(techs)) + "):", ', '.join(techs[:8]) or '(none)')
    print("  categories    (" + str(len(cats))  + "):", ', '.join(cats) or '(none)')
    print("  methodologies (" + str(len(meths)) + "):", ', '.join(meths[:6]) or '(none)')
    print()

print("=== FTS SEARCHABILITY ===\n")
tests = [
    ("diffusion",       "Diffusion"),
    ("counterfactual",  "Causal Contrastive"),
    ("federated",       "Federated Learning"),
    ("graph coarsening","Graph Coarsening"),
    ("surrogate",       "Surrogate"),
]
all_pass = True
for query, fragment in tests:
    hits = conn.execute(
        "SELECT p.title FROM entities_fts ef JOIN papers p ON p.id=ef.paper_id "
        "WHERE entities_fts MATCH ? LIMIT 5", (query,)
    ).fetchall()
    titles = [h[0] for h in hits]
    found = any(fragment.lower() in t.lower() for t in titles)
    if not found:
        all_pass = False
    status = "PASS" if found else "FAIL"
    first = titles[0][:70] if titles else "(no hits)"
    print("  [" + status + "] '" + query + "' -> " + first)

print()
print("FTS overall:", "ALL PASS" if all_pass else "SOME FAILURES")
conn.close()
