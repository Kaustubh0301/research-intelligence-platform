# Rebuild Runbook — Full-Text Source Upgrade

**Date:** 2026-06-05  
**Purpose:** Safe execution guide for upgrading 90 abstract-only NotebookLM sources to full-text  
**Prerequisites read:** `UPGRADE_PATH_AUDIT.md`, `EXPECTED_REBUILD_IMPACT.md`  
**Status:** AWAITING APPROVAL — do not execute without review

---

## Irreversibility Map

The single most important thing to understand before executing: **this procedure has one point of no return**, and it is on the NotebookLM side, not the database side.

| Operation | Reversible? | Recovery method |
|---|---|---|
| `cp research_platform.db research_platform.db.backup` | — | N/A (this IS the recovery) |
| Export synthesis content to file | — | N/A (this IS the recovery) |
| `nlm notebook delete <id> --confirm` | **NO** | Cannot be undone. Notebook and all its sources are permanently destroyed in NotebookLM. A DB backup does NOT restore NLM notebooks. |
| `UPDATE notebooks SET notebooklm_id=NULL` | Yes | `cp research_platform.db.backup research_platform.db` |
| `UPDATE notebook_papers SET source_status='pending'` | Yes | Same DB restore |
| `DELETE FROM notebook_syntheses` | Yes (with export) | Restore from DB backup OR re-import from exported file |
| Stage B (provision new notebooks) | Yes | Delete new notebooks, restore DB from backup |
| Stage C (upload sources) | Yes | Delete notebooks, restore DB from backup |
| Stage D (synthesize) | Yes | Re-run Stage D |
| Stage E (extract) | Partial | Old extraction rows NOT deleted — Stage E appends and updates, it does not wipe |
| `normalize_entities.py` | Yes | Re-run with older alias maps or restore from backup |
| `build_graph_v2.py` | Yes | Re-run |

**The point of no return is Step 4: `nlm notebook delete`.** Everything before it is fully reversible. After it, the NLM side cannot be restored regardless of what happens to the local DB.

---

## Rollback Procedures

### Full rollback (before any NLM deletion)

If you need to abort before starting Step 4:

```bash
# Nothing has changed yet — no action needed.
# The backup exists but the live DB is untouched.
```

### Partial rollback (after some NLM notebooks deleted, before DB reset)

NLM notebooks already deleted cannot be recovered. DB is still in original state.

**Safe path:** continue to delete the remaining notebooks (do not try to restore deleted ones), then proceed with Step 5 (DB reset) and continue the procedure. Aborting mid-deletion leaves a split state where some notebooks exist in NLM but others do not. The DB reset in Step 5 handles this correctly — it NULLs all `notebooklm_id` values regardless.

**Do not restore the DB backup at this point** — the backup still contains the IDs of now-deleted NLM notebooks, which would leave the DB pointing to non-existent notebooks.

### Rollback after DB reset (Steps 5–6) but before pipeline stages

```bash
# Restore DB from backup
cp research_platform.db.backup research_platform.db

# Verify restore
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM notebook_syntheses'); print('Syntheses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL'); print('Notebooks with NLM ID:', c.fetchone()[0])
"
# Expected: Syntheses: 115, Notebooks with NLM ID: 23
# NOTE: The restored DB will reference NLM notebook IDs that no longer exist.
# Those IDs are invalid — Stage B will fail if run against them.
# You must proceed with the rebuild (delete remaining notebooks → Step 5 onward).
```

### Rollback after Stage E (extraction overwritten)

Stage E does not delete existing technique/analysis rows — it upserts. Old abstract-derived rows remain. New full-text-derived rows are added or updated. A DB backup from before Stage E is the only way to return to the exact pre-upgrade extraction state.

---

## Backup Strategy

**Two backups are required before Step 4. Both must be confirmed before proceeding.**

### Backup 1 — Full DB snapshot

```bash
cp research_platform.db research_platform.db.backup_$(date +%Y%m%d_%H%M%S)
```

Verify:
```bash
ls -lh research_platform.db research_platform.db.backup_*
# Sizes must match exactly
python3 -c "
import os
orig = os.path.getsize('research_platform.db')
import glob; backups = sorted(glob.glob('research_platform.db.backup_*'))
bak = os.path.getsize(backups[-1])
print(f'Original: {orig} bytes')
print(f'Backup:   {bak} bytes')
print('MATCH' if orig == bak else 'SIZE MISMATCH — DO NOT PROCEED')
"
```

### Backup 2 — Synthesis content export

The 115 `notebook_syntheses` rows contain the actual text responses from NotebookLM. These are permanently lost after `DELETE FROM notebook_syntheses`. Export them first:

```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('research_platform.db')
c = conn.cursor()
c.execute('''
    SELECT ns.id, n.topic_slug, n.instance_number, ns.synthesis_type,
           ns.query_prompt, ns.content, ns.word_count, ns.normalized, ns.created_at
    FROM notebook_syntheses ns
    JOIN notebooks n ON n.id = ns.notebook_id
    ORDER BY n.topic_slug, ns.query_prompt
''')
rows = [dict(zip([d[0] for d in c.description], r)) for r in c.fetchall()]
with open('synthesis_backup_$(date +%Y%m%d_%H%M%S).json', 'w') as f:
    json.dump(rows, f, indent=2, default=str)
print(f'Exported {len(rows)} synthesis rows')
conn.close()
" 
```

Verify:
```bash
python3 -c "
import json, glob
f = sorted(glob.glob('synthesis_backup_*.json'))[-1]
data = json.load(open(f))
print(f'Backup file: {f}')
print(f'Rows: {len(data)}')
print(f'Unique notebooks: {len(set(r[\"topic_slug\"] for r in data))}')
print(f'Unique prompts: {len(set(r[\"query_prompt\"] for r in data))}')
"
# Expected: 115 rows, 23 notebooks, 5 prompts
```

### Backup 3 — Notebook ID registry (optional but recommended)

```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('research_platform.db')
c = conn.cursor()
c.execute('SELECT id, topic_slug, instance_number, notebooklm_id, notebooklm_url, source_count, status FROM notebooks ORDER BY topic_slug, instance_number')
rows = [dict(zip([d[0] for d in c.description], r)) for r in c.fetchall()]
with open('notebook_registry_backup_$(date +%Y%m%d_%H%M%S).json', 'w') as f:
    json.dump(rows, f, indent=2)
print(f'Exported {len(rows)} notebook rows')
conn.close()
"
```

---

## Execution Sequence

### Step 0 — Verify prerequisites

```bash
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# 0a. Confirm paper_sections coverage
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_sections'); print('Sections:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM papers WHERE pdf_local_path IS NOT NULL'); print('PDFs on disk:', c.fetchone()[0])
"
# Required: sections >= 95 before proceeding
# Current known state: 98 papers with sections

# 0b. Confirm NotebookLM auth
nlm notebook list --json | python3 -c "
import sys, json; d=json.load(sys.stdin)
print(f'Auth OK — {len(d)} notebooks visible in NLM')
"
# Required: returns 23 notebooks (matching DB count)
# If auth expired: nlm login

# 0c. Confirm DB baseline
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers'); print('Papers:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebook_syntheses'); print('Syntheses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebooks'); print('Notebooks:', c.fetchone()[0])
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status'); print('Statuses:', c.fetchall())
"
# Required: Papers=100, Syntheses=115, Notebooks=23
# Required: abstract_only=150, uploaded=20
```

**STOP if any check fails.** Do not proceed until all three pass.

---

### Step 1 — Take Backup 1 (DB snapshot)

```bash
cp research_platform.db research_platform.db.backup_$(date +%Y%m%d_%H%M%S)
```

**Checkpoint 1:**
```bash
python3 -c "
import os, glob
orig = os.path.getsize('research_platform.db')
bak  = os.path.getsize(sorted(glob.glob('research_platform.db.backup_*'))[-1])
print(f'Original: {orig:,} bytes | Backup: {bak:,} bytes | Match: {orig==bak}')
"
# Required: Match=True
```

**STOP if checkpoint fails.**

---

### Step 2 — Take Backup 2 (synthesis export)

```bash
python3 - << 'PYEOF'
import sqlite3, json, datetime
conn = sqlite3.connect('research_platform.db')
c = conn.cursor()
c.execute('''
    SELECT ns.id, n.topic_slug, n.instance_number, ns.synthesis_type,
           ns.query_prompt, ns.content, ns.word_count, ns.normalized,
           ns.created_at
    FROM notebook_syntheses ns
    JOIN notebooks n ON n.id = ns.notebook_id
    ORDER BY n.topic_slug, ns.query_prompt
''')
rows = [dict(zip([d[0] for d in c.description], r)) for r in c.fetchall()]
fname = f"synthesis_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(fname, 'w') as f:
    json.dump(rows, f, indent=2, default=str)
print(f'Exported {len(rows)} rows to {fname}')
conn.close()
PYEOF
```

**Checkpoint 2:**
```bash
python3 -c "
import json, glob
f = sorted(glob.glob('synthesis_backup_*.json'))[-1]
data = json.load(open(f))
topics = set(r['topic_slug'] for r in data)
prompts = set(r['query_prompt'] for r in data)
print(f'File: {f}')
print(f'Rows: {len(data)} (expected 115)')
print(f'Notebooks: {len(topics)} (expected 23)')
print(f'Prompts: {len(prompts)} (expected 5): {sorted(prompts)}')
"
# Required: Rows=115, Notebooks=23, Prompts=5
```

**STOP if checkpoint fails.**

---

### Step 3 — Take Backup 3 (notebook registry)

```bash
python3 - << 'PYEOF'
import sqlite3, json, datetime
conn = sqlite3.connect('research_platform.db')
c = conn.cursor()
c.execute('SELECT id, topic_slug, instance_number, notebooklm_id, notebooklm_url, source_count, status FROM notebooks ORDER BY topic_slug, instance_number')
rows = [dict(zip([d[0] for d in c.description], r)) for r in c.fetchall()]
fname = f"notebook_registry_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(fname, 'w') as f:
    json.dump(rows, f, indent=2)
print(f'Exported {len(rows)} notebooks')
for r in rows:
    print(f"  {r['topic_slug']}-{r['instance_number']}: nlm_id={r['notebooklm_id']}")
conn.close()
PYEOF
```

**Checkpoint 3:** Confirm output shows 23 lines each with a non-null `nlm_id`.

---

### Step 4 — Delete NLM notebooks  ⚠️ POINT OF NO RETURN

**Read before executing:**
- Each `nlm notebook delete` is permanent and cannot be undone
- If auth expires mid-deletion, re-auth with `nlm login` and continue from where you stopped
- Do NOT update the DB until all deletions are complete
- Track which notebooks have been deleted using the registry exported in Step 3

**Get the list of IDs to delete:**
```bash
python3 -c "
import sqlite3
c = sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT topic_slug, instance_number, notebooklm_id FROM notebooks ORDER BY topic_slug, instance_number')
for r in c.fetchall():
    print(f'nlm notebook delete {r[2]} --confirm   # {r[0]}-{r[1]}')
"
# Prints 23 commands — review before running
```

**Execute deletions one at a time:**
```bash
# Run each command printed above individually.
# After each deletion, confirm with:
nlm notebook list --json | python3 -c "
import sys, json; d=json.load(sys.stdin)
print(f'{len(d)} notebooks remaining in NLM')
"
```

**Checkpoint 4:**
```bash
nlm notebook list --json | python3 -c "
import sys, json; d=json.load(sys.stdin)
remaining = len(d)
print(f'NLM notebooks remaining: {remaining}')
print('PASS' if remaining == 0 else f'FAIL — {remaining} notebooks still exist in NLM')
"
# Required: 0 notebooks remaining in NLM
```

**STOP if any notebooks remain.** Find and delete them before proceeding.

---

### Step 5 — Reset the database

Only execute after Checkpoint 4 passes (NLM side confirmed empty).

```bash
python3 - << 'PYEOF'
import sqlite3
conn = sqlite3.connect('research_platform.db')
c = conn.cursor()

# Reset notebooks — clear NLM IDs and counters
c.execute("""
    UPDATE notebooks
    SET notebooklm_id   = NULL,
        notebooklm_url  = NULL,
        source_count    = 0,
        status          = 'active',
        last_synced_at  = NULL
""")
nb_updated = c.rowcount
print(f'Notebooks reset: {nb_updated}')

# Reset notebook_papers — all back to pending
c.execute("""
    UPDATE notebook_papers
    SET source_status         = 'pending',
        upload_attempted_at   = NULL,
        upload_completed_at   = NULL
""")
np_updated = c.rowcount
print(f'notebook_papers reset: {np_updated}')

# Delete synthesis rows (already backed up in Step 2)
c.execute("DELETE FROM notebook_syntheses")
synth_deleted = c.rowcount
print(f'notebook_syntheses deleted: {synth_deleted}')

conn.commit()
conn.close()
print('DB reset committed.')
PYEOF
```

**Checkpoint 5:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL')
nlm_ids = c.fetchone()[0]
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
statuses = dict(c.fetchall())
c.execute('SELECT COUNT(*) FROM notebook_syntheses')
synths = c.fetchone()[0]
print(f'Notebooks with notebooklm_id: {nlm_ids} (expected 0)')
print(f'notebook_papers statuses: {statuses} (expected all pending)')
print(f'notebook_syntheses: {synths} (expected 0)')
all_ok = nlm_ids==0 and statuses.get('pending',0)==170 and synths==0
print('PASS' if all_ok else 'FAIL — investigate before proceeding')
"
# Required: 0 notebooks with nlm_id, all 170 notebook_papers pending, 0 syntheses
```

**STOP if checkpoint fails.** If the reset ran but the commit failed, restore from backup (Step 1 backup) and retry.

---

### Step 6 — Stage B: Provision new notebooks

```bash
python -m notebooklm.run_pipeline --stage provision
```

This calls `nlm notebook create` for each of the 23 `notebooks` rows that now have `notebooklm_id=NULL`. Each new notebook gets a fresh `notebooklm_id` and `notebooklm_url` written to the DB.

**Checkpoint 6:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL')
provisioned = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebooks')
total = c.fetchone()[0]
print(f'Provisioned: {provisioned}/{total}')
print('PASS' if provisioned == total else f'FAIL — {total-provisioned} notebooks not provisioned')
"
# Required: provisioned == 23
```

If provisioning partially fails (auth timeout, rate limit): re-run `--stage provision` — it skips already-provisioned notebooks (`notebooklm_id != None`) and only creates the missing ones.

---

### Step 7 — Stage C: Upload sources

Upload in batches of 50 to allow checkpointing and manage session length.

```bash
# Batch 1
python -m notebooklm.run_pipeline --stage upload --limit 50

# Checkpoint after batch 1
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
print('Status breakdown:', dict(c.fetchall()))
"

# Batch 2
python -m notebooklm.run_pipeline --stage upload --limit 50

# Batch 3
python -m notebooklm.run_pipeline --stage upload --limit 50

# Batch 4 (remaining ~20)
python -m notebooklm.run_pipeline --stage upload --limit 50
```

If auth expires mid-batch: `nlm login`, then re-run `--stage upload --limit 50`. Already-uploaded rows are skipped (`source_status != 'pending'`).

**Checkpoint 7:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
statuses = dict(c.fetchall())
pending  = statuses.get('pending', 0)
uploaded = statuses.get('uploaded', 0)
ao       = statuses.get('abstract_only', 0)
errors   = statuses.get('error', 0)
total    = sum(statuses.values())
print(f'pending={pending}  uploaded={uploaded}  abstract_only={ao}  error={errors}  total={total}')
print()
# Verify quality improvement
c.execute('SELECT COUNT(DISTINCT paper_id) FROM notebook_papers WHERE source_status=\"uploaded\"')
full_text_papers = c.fetchone()[0]
c.execute('SELECT COUNT(DISTINCT paper_id) FROM notebook_papers WHERE source_status=\"abstract_only\"')
ao_papers = c.fetchone()[0]
print(f'Distinct papers uploaded full-text:    {full_text_papers} (was 10, target >= 95)')
print(f'Distinct papers still abstract-only:   {ao_papers} (was 90, target <= 5)')
print('PASS' if pending == 0 and uploaded >= 150 else 'FAIL or incomplete')
"
# Required: pending=0, no items stuck in error
# Expected: uploaded ~162-170 (98 papers × ~1.7 assignments)
# Expected: abstract_only ~2-8 (papers with no paper_sections)
# Expected: ~2 papers with no sections stay abstract_only
```

**If errors > 0:** Check `pipeline_errors` table and investigate before proceeding:
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT stage, error_type, error_msg FROM pipeline_errors ORDER BY created_at DESC LIMIT 10')
for r in c.fetchall(): print(r)
"
```

---

### Step 8 — Stage D: Synthesize

```bash
python -m notebooklm.run_pipeline --stage synthesize
```

Stage D will skip notebooks that still have `pending` rows — it waits until all sources in a notebook are uploaded. After Checkpoint 7 passes, no pending rows exist, so all notebooks are eligible.

Stage D sends 5 prompts per notebook. Each prompt call has a 5-second sleep between them (`_QUERY_SLEEP_S = 5`). At ~20 notebooks × 5 prompts × ~30s per call = ~50–60 minutes.

**Checkpoint 8:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM notebook_syntheses'); total_synths = c.fetchone()[0]
c.execute('SELECT COUNT(DISTINCT notebook_id) FROM notebook_syntheses'); nb_with_synths = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0'); unnorm = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL'); total_nbs = c.fetchone()[0]
expected = total_nbs * 5
print(f'Synthesis rows: {total_synths} (expected ~{expected})')
print(f'Notebooks with syntheses: {nb_with_synths}/{total_nbs}')
print(f'Rows ready for extraction (normalized=False): {unnorm}')
print('PASS' if total_synths >= expected * 0.9 else 'FAIL — missing syntheses')
"
# Required: synthesis rows >= 90% of expected (some notebooks may have been empty/skipped)
# Required: normalized=False count > 0 (needed for Stage E to run)
```

If synthesis is incomplete (some notebooks failed): re-run `--stage synthesize`. Stage D skips notebooks that already have all 5 prompts answered.

---

### Step 9 — Stage E: Extract

```bash
python -m notebooklm.run_pipeline --stage extract
```

Stage E processes all notebooks with `normalized=False` synthesis rows. It writes to `paper_analyses`, `paper_techniques`, `paper_datasets`, `paper_categories`, `paper_methodologies`.

**Important:** Stage E upserts — it does not delete existing extraction rows before writing. Old abstract-derived rows that also appear in the new synthesis will be updated (role and name may change). Techniques that only appeared in the old abstract-derived synthesis but not in the new full-text synthesis will **remain** in the DB. This is additive, not a clean replacement. The net effect is more rows, not fewer.

**Checkpoint 9:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('paper_analyses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_techniques'); print('paper_techniques:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE role=\"introduces\"'); print('introduces rows:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_datasets'); print('paper_datasets:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0'); print('un-normalized remaining:', c.fetchone()[0])
"
# Expected vs current (before upgrade):
#   paper_analyses:  100 (unchanged — upsert by paper_id)
#   paper_techniques: 655 → target ~1,100-1,295 (significant increase)
#   introduces rows:  233 → target ~380-464 (significant increase)
#   paper_datasets:   49  → target ~200-294 (large increase)
#   un-normalized: 0 (all processed)
```

---

### Step 10 — Re-normalize entities

```bash
python normalize_entities.py
```

Re-runs the two-pass alias normalization over all `paper_techniques` and `paper_datasets` rows, including the newly extracted ones. Writes/updates `canonical_name`.

**Checkpoint 10:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL')
print('Techniques missing canonical_name:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques WHERE canonical_name IS NOT NULL')
print('Distinct canonical techniques:', c.fetchone()[0])
"
# Required: 0 missing canonical_name
# Expected: distinct canonical count significantly higher than 517 (pre-upgrade)
```

---

### Step 11 — Rebuild graph

```bash
python build_graph_v2.py
```

Recomputes IDF weights on the upgraded corpus and rebuilds `paper_relationships`, `entity_relationships`, `paper_graph_metrics`, `technique_graph_metrics`.

**Checkpoint 11:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_relationships'); edges = c.fetchone()[0]
c.execute('SELECT AVG(weight) FROM paper_relationships'); avg_w = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM paper_relationships WHERE technique_score > 0'); tech_edges = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM (SELECT canonical_name FROM paper_techniques WHERE canonical_name IS NOT NULL GROUP BY canonical_name HAVING COUNT(DISTINCT paper_id) >= 2)')
shared = c.fetchone()[0]
print(f'Paper edges: {edges} (was 2517, expected 2800-3200)')
print(f'Avg weight:  {avg_w:.3f} (was 1.339, expected 1.8-2.2)')
print(f'Tech edges:  {tech_edges} (was 85, expected 400-600)')
print(f'Shared techniques: {shared} (was 19, expected 100-150)')
"
```

---

### Step 12 — Run audit scripts to validate impact

```bash
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py
```

Compare outputs in `outputs/` against pre-upgrade baseline. Key targets:
- Singleton percentage: 96.3% → target < 80%
- SHARED-tier techniques: 2 → target ≥ 20

---

## Summary: Execution Order and Go/No-Go Gates

```
Step 0  Verify prerequisites          ──────── STOP if auth fails or sections < 95
Step 1  Backup DB                     ──────── STOP if sizes don't match
Step 2  Export synthesis to JSON      ──────── STOP if row count != 115
Step 3  Export notebook registry      ──────── STOP if row count != 23
         ↓
         ═══ POINT OF NO RETURN ═══
Step 4  Delete NLM notebooks          ──────── STOP if any notebooks remain after all deletions
         ═══ POINT OF NO RETURN ═══
         ↓
Step 5  Reset DB                      ──────── STOP if pending count != 170 or syntheses != 0
Step 6  Stage B: Provision            ──────── STOP if provisioned != 23; re-run to retry
Step 7  Stage C: Upload (4 batches)   ──────── STOP if errors > 0; investigate
Step 8  Stage D: Synthesize           ──────── Re-run if incomplete; idempotent
Step 9  Stage E: Extract              ──────── Re-run if un-normalized > 0; idempotent
Step 10 normalize_entities.py         ──────── Re-run safely; idempotent
Step 11 build_graph_v2.py             ──────── Re-run safely; idempotent
Step 12 Audit scripts                 ──────── Compare against baseline
```

**Estimated total time:** 2.5–3.5 hours  
**Estimated NLM calls:** ~260–280 incremental  
**Estimated risk:** Low if backups confirmed before Step 4; irreversible only on NLM side

---

## What to Do If This Runbook Gets Interrupted

| Interrupted at | State | Recovery action |
|---|---|---|
| Before Step 4 | DB unchanged, backups taken | Start again from Step 4 |
| During Step 4 (some notebooks deleted) | NLM partial, DB unchanged | Continue deleting remaining notebooks, then proceed to Step 5 |
| After Step 4, before Step 5 | NLM empty, DB still has old IDs | Proceed directly to Step 5 |
| During Step 5 (DB reset failed) | Possible partial state | Restore DB from Step 1 backup, repeat Step 5 |
| During Step 6 (partial provisioning) | Some notebooks provisioned | Re-run `--stage provision`; skips already-provisioned |
| During Step 7 (partial uploads) | Some papers uploaded | Re-run `--stage upload --limit 50`; skips non-pending rows |
| During Step 8 (partial synthesis) | Some synthesized | Re-run `--stage synthesize`; skips complete notebooks |
| After Step 9 (extraction complete) | New data written | Proceed to Step 10; extraction is complete |
