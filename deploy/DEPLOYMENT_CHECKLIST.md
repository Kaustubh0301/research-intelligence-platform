# Deployment Runbook — Research Intelligence Platform (Demo)

Single VPS · Docker Compose · SQLite · nginx TLS

Work through each section in order. Every step has a verification command.

---

## Architecture

```
Browser
  │
  ▼  443/80
nginx (nginx:1.27-alpine)
  ├──/api/v1/*    → api:8000  (FastAPI + uvicorn, 2 workers)
  └──/*           → web:3000  (Next.js 15)

Volumes (on VPS host, bind-mounted):
  ./research_platform.db  → /data/research_platform.db  (rw, SQLite WAL)
  ./embeddings.index      → /data/embeddings.index      (ro, FAISS)
  ./embeddings_ids.json   → /data/embeddings_ids.json   (ro, FAISS IDs)

Baked into API image:
  /app/.hf_cache/  — all-MiniLM-L6-v2 model (88 MB, offline)
```

---

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| VPS CPU | 4 vCPU | 2 uvicorn workers each load ~90 MB model |
| VPS RAM | 8 GB | 2 workers × ~500 MB RSS + OS + nginx + Next.js |
| VPS Disk | 40 GB | DB 656 MB + images ~4 GB + headroom |
| OS | Ubuntu 22.04 LTS | |
| Docker | 24+ | `docker compose` (v2, no hyphen) |
| Domain | A record → VPS IP | TTL ≤ 300s recommended |
| Ports | 80, 443 open | In VPS firewall and security group |
| Anthropic key | Yes | Direct API access (api.anthropic.com) |

---

## Step 0 — One-time prep on your local machine

These run once before you push to the VPS.

### 0a. Enable WAL mode on the SQLite database

**Required.** The two uvicorn workers both read/write the same file. Without WAL
mode, concurrent writes return `OperationalError: database is locked`.

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('research_platform.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA wal_autocheckpoint=1000')
print(conn.execute('PRAGMA journal_mode').fetchone())
conn.close()
"
# Expected output: ('wal',)
```

This has already been run — `journal_mode` is now `wal`.

### 0b. Verify the HuggingFace model cache is present

```bash
ls .hf_cache/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/
du -sh .hf_cache/hub/
# Expected: ~88 MB
```

### 0c. Build and smoke-test locally (optional but recommended)

```bash
# Set NEXT_PUBLIC_API_URL to your domain before building
export NEXT_PUBLIC_API_URL=https://yourdomain.com/api/v1
export ANTHROPIC_API_KEY=sk-ant-...
export CORS_ORIGIN=https://yourdomain.com

docker compose --env-file .env.production build
docker compose --env-file .env.production up -d

curl -sf http://localhost/health   # nginx → api (HTTP, before TLS)
```

---

## Step 1 — VPS setup

```bash
# Install Docker (Ubuntu 22.04)
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER && newgrp docker
docker --version          # ≥ 24
docker compose version    # v2.x (no hyphen)

# Create app directory
mkdir -p /srv/rip
cd /srv/rip
```

---

## Step 2 — Clone the repository

```bash
git clone <your-repo-url> /srv/rip
cd /srv/rip
```

If the repo is private, set up an SSH deploy key or use a personal access token.

---

## Step 3 — Copy runtime data files

These files are **not in git** (excluded by .gitignore). SCP from your local machine:

```bash
# From your local machine:
scp research_platform.db    user@<VPS_IP>:/srv/rip/research_platform.db
scp embeddings.index        user@<VPS_IP>:/srv/rip/embeddings.index
scp embeddings_ids.json     user@<VPS_IP>:/srv/rip/embeddings_ids.json
rsync -a --progress .hf_cache/ user@<VPS_IP>:/srv/rip/.hf_cache/
```

Verify on the VPS:

```bash
ls -lh /srv/rip/research_platform.db      # ~656 MB
ls -lh /srv/rip/embeddings.index          # ~9.7 MB
ls -lh /srv/rip/embeddings_ids.json       # ~483 KB
du -sh /srv/rip/.hf_cache/hub/            # ~88 MB
```

Verify WAL mode survived the copy:

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('/srv/rip/research_platform.db')
print(c.execute('PRAGMA journal_mode').fetchone())
"
# Expected: ('wal',)
# If it shows 'delete', re-run Step 0a on the copied file.
```

- [ ] `research_platform.db` present, ~656 MB, WAL mode confirmed
- [ ] `embeddings.index` present
- [ ] `embeddings_ids.json` present
- [ ] `.hf_cache/hub/models--sentence-transformers--all-MiniLM-L6-v2/` present

---

## Step 4 — Create the production environment file

```bash
cd /srv/rip
cp .env.production.example .env.production
nano .env.production
```

Fill in every value:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `sqlite:////data/research_platform.db` | Four slashes — absolute path inside container |
| `LLM_PROVIDER` | `anthropic` | |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Your Anthropic API key |
| `ANTHROPIC_BASE_URL` | *(leave blank)* | Leave empty to use api.anthropic.com directly. **Do not use the internal proxy URL — it is not reachable from a VPS.** |
| `GEMINI_API_KEY` | *(leave blank if using Anthropic)* | |
| `CORS_ORIGIN` | `https://yourdomain.com` | Exact origin, no trailing slash |
| `NEXT_PUBLIC_API_URL` | `https://yourdomain.com/api/v1` | Baked into Next.js bundle at build time |
| `SEMANTIC_SEARCH` | `true` | |

```bash
# Confirm no value is missing
grep "=$" .env.production   # should show only optional blank lines
```

- [ ] `.env.production` created
- [ ] `ANTHROPIC_API_KEY` set
- [ ] `CORS_ORIGIN` and `NEXT_PUBLIC_API_URL` set to the real domain
- [ ] `ANTHROPIC_BASE_URL` is blank (not the internal proxy)

---

## Step 5 — TLS certificate

```bash
apt-get install -y certbot
# Stop anything on port 80 first (or use --webroot if nginx is running)
certbot certonly --standalone -d yourdomain.com

mkdir -p /srv/rip/deploy/certs
ln -s /etc/letsencrypt/live/yourdomain.com/fullchain.pem /srv/rip/deploy/certs/fullchain.pem
ln -s /etc/letsencrypt/live/yourdomain.com/privkey.pem   /srv/rip/deploy/certs/privkey.pem

ls -l /srv/rip/deploy/certs/   # both symlinks should resolve
```

**No domain yet?** Comment out the HTTPS server block in `deploy/nginx/conf.d/rip.conf`
and expose port 80 only while testing. The `/health` endpoint works over HTTP.

- [ ] Certs present at `deploy/certs/fullchain.pem` and `deploy/certs/privkey.pem`

---

## Step 6 — Set the domain in nginx config

```bash
sed -i 's/yourdomain.com/YOUR_ACTUAL_DOMAIN/g' /srv/rip/deploy/nginx/conf.d/rip.conf
grep server_name /srv/rip/deploy/nginx/conf.d/rip.conf   # confirm change
```

- [ ] `server_name` in `rip.conf` matches your domain

---

## Step 7 — Build images and start

First build (takes 10–20 min — torch wheel is ~1 GB):

```bash
cd /srv/rip
docker compose --env-file .env.production build
```

Expected image sizes:
- `rip-api:latest` — ~3.5 GB (torch + sentence-transformers + HF model)
- `rip-web:latest` — ~500 MB (Next.js + node_modules)

Start all services:

```bash
docker compose --env-file .env.production up -d
```

Check all three services are running:

```bash
docker compose ps
# Expected: api (healthy), web (healthy), nginx (running)
```

Watch startup (API takes ~10s to load FAISS + model):

```bash
docker compose logs -f api
# Expected lines:
#   Loading sentence-transformers model all-MiniLM-L6-v2 …
#   Loading FAISS index from /data/embeddings.index …
#   Semantic index ready — XXXX chunks across 2510 papers
#   Application startup complete.
```

- [ ] All three containers `running` / `healthy`
- [ ] API log shows `Semantic index ready`

---

## Step 8 — Smoke tests

```bash
# Health check
curl -sf https://yourdomain.com/health && echo "OK"
# Expected: {"status":"ok","db":"connected"}

# Stats (verifies DB is accessible and has data)
curl -sf https://yourdomain.com/api/v1/stats | python3 -m json.tool | grep total_papers
# Expected: "total_papers": 2510

# Search (verifies FTS retrieval)
curl -sf -X POST https://yourdomain.com/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer", "limit": 3}' | python3 -m json.tool | grep total
# Expected: "total": 282

# Chat (verifies Anthropic API key and FAISS semantic search)
curl -sf -X POST https://yourdomain.com/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is LoRA?", "history": []}' | python3 -m json.tool | grep answer
# Expected: answer field with content (~12-15s)

# SSE streaming (verifies nginx proxy_buffering off)
curl -N -X POST https://yourdomain.com/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "What is LoRA?", "history": []}' 2>&1 | head -10
# Expected: data: {"type":"sources",...} then data: {"type":"token",...} lines arriving
# incrementally — NOT all at once after a long pause.

# Frontend
curl -sf https://yourdomain.com/ | grep -o '<title>.*</title>'
```

- [ ] `/health` returns `{"status":"ok","db":"connected"}`
- [ ] `/api/v1/stats` returns `total_papers: 2510`
- [ ] Search returns results
- [ ] Chat returns an answer (confirms API key is working)
- [ ] SSE tokens arrive incrementally
- [ ] Frontend `<title>` tag present

---

## Step 9 — Feature Mapper smoke test

The analyze endpoint makes multiple concurrent LLM calls (~55-115s). Verify
nginx does NOT cut it off at 60s (the `/api/v1/feature-map/analyze` location
block in `rip.conf` sets `proxy_read_timeout 180s`).

```bash
curl -sf -X POST https://yourdomain.com/api/v1/feature-map/analyze \
  -H "Content-Type: application/json" \
  --max-time 180 \
  -d '{
    "text": "# Hybrid Search\n\nThis system uses BM25 sparse retrieval via Pyserini over an inverted index for lexical matching. The index covers 50 million documents. Queries use a custom whitespace tokenizer with Unicode normalization and are answered in under 50ms at p99. In addition to sparse retrieval, we use a bi-encoder DPR model with FAISS for dense semantic search. The two signals are fused using Reciprocal Rank Fusion with k=60 to produce the final ranked list of results returned to the user."
  }' | python3 -m json.tool | grep -E "feature_count|total_duration"
# Expected: feature_count >= 2, total_duration_ms in the 30000–120000 range
```

- [ ] Feature mapper returns results within 180s without 504 error

---

## Step 10 — Post-deployment hardening

```bash
# Auto-renew TLS
echo "0 3 * * * root certbot renew --quiet --deploy-hook 'docker compose -f /srv/rip/docker-compose.yml restart nginx'" \
  >> /etc/crontab

# Log rotation (prevent unbounded growth)
cat > /etc/logrotate.d/rip-docker << 'EOF'
/var/lib/docker/containers/*/*.log {
  daily
  rotate 7
  compress
  missingok
  copytruncate
}
EOF

# Uptime monitor — send a GET /health every minute
echo "* * * * * root curl -sf https://yourdomain.com/health > /dev/null || \
  systemctl restart docker" >> /etc/crontab

# Enable HSTS once HTTPS is confirmed working (uncomment in rip.conf):
# add_header Strict-Transport-Security "max-age=63072000" always;
```

- [ ] Certbot renewal cron set up
- [ ] Log rotation configured
- [ ] `/docs` and `/redoc` endpoints gated or removed if public-facing

---

## Known issues and mitigations

| Issue | Impact | Status | Fix |
|-------|--------|--------|-----|
| Feature mapper `/analyze` takes 55–115s | 504 if nginx timeout too short | **Fixed** — `proxy_read_timeout 180s` for `/api/v1/feature-map/analyze` |
| SQLite `journal_mode=delete` default | Concurrent writer lock errors with 2 workers | **Fixed** — WAL mode enabled on DB file (step 0a) |
| `ANTHROPIC_BASE_URL` internal proxy | Unreachable from VPS | **Documented** — leave blank for direct api.anthropic.com access |
| `corpus_intel/` was copied into image | ~308 KB dead weight | **Fixed** — removed from Dockerfile.api COPY list |
| `version: "3.9"` in docker-compose.yml | Deprecation warning | **Fixed** — field removed |
| `NEXT_PUBLIC_API_URL` baked at build time | Cannot be overridden at runtime | **By design** — must set correct domain before `docker compose build` |
| SQLite not suitable for high concurrency | Write bottleneck above ~10 concurrent writers | **Acceptable** for demo (<20 internal users); PostgreSQL migration is the next step if needed |
| `rip-api` image ~3.5 GB | Slow first push/pull | Pre-pull or use a container registry |
| No standalone Next.js output | Web image copies full node_modules (~500 MB) | Add `output: "standalone"` to `next.config.ts` to reduce to ~150 MB |
| Docker not installed on dev machine | Cannot test build locally | Build on the VPS itself; images are architecture-specific anyway |
| Extraction LLM call uses same proxy | Proxy latency is ~15s/call baseline | Not a blocker — works with direct Anthropic API |

---

## SQLite deployment viability

SQLite is appropriate for this demo:

- **Read-heavy workload** — 2,510 papers, mostly SELECT queries
- **WAL mode** (now enabled) allows concurrent reads + one writer at a time
- **Write load** — only chat sessions and feature-map results are written; low frequency
- **Failure mode** — SQLite never loses data; worst case is a temporary lock error on concurrent writes
- **Upgrade path** — `DATABASE_URL` in `.env.production` accepts a PostgreSQL URL; `db/session.py` uses SQLAlchemy ORM throughout; the only SQLite-specific code is `search/fts.py` (FTS5 virtual tables) which has an `except Exception: return []` fallback, so FTS silently degrades and FAISS/graph retrieval continues to work

**Switch to PostgreSQL when:** more than 3–5 concurrent users start hitting write endpoints simultaneously, or when the demo graduates to a persistent service.

---

## Storage and memory sizing

| Component | Size | Notes |
|-----------|------|-------|
| `research_platform.db` | 656 MB | SQLite, WAL mode |
| `embeddings.index` | 9.7 MB | FAISS FlatIP, 384-dim |
| `embeddings_ids.json` | 483 KB | |
| `.hf_cache/` (in image) | 88 MB | all-MiniLM-L6-v2, offline |
| `rip-api` Docker image | ~3.5 GB | torch dominates |
| `rip-web` Docker image | ~500 MB | |
| **Per-worker RSS** | ~500 MB | Measured: 463 MB at idle (model + FAISS loaded) |
| **2 workers total** | ~1 GB | + 200 MB OS headroom = 1.2 GB minimum for API |
| **Full stack** | ~1.5 GB | api + web + nginx + OS |
| **Recommended VPS** | 8 GB RAM / 40 GB disk | 4 vCPU for parallel LLM calls |

---

## PostgreSQL migration — only if required

Not needed for the demo. When the time comes:

**Code changes required:**
1. `search/fts.py:61` — `sqlite_master` → `pg_tables` (or drop FTS, rely on FAISS)
2. `db/migrate.py` — FTS5 DDL uses `CREATE VIRTUAL TABLE ... USING fts5(...)` — not valid in Postgres
3. `search/sync.py:27` — `SQLITE_IN_LIMIT = 900` SQLite-specific workaround, remove
4. `search/metadata.py` — hex UUID storage (`hex_ids`, `uuid_by_hex`) — remove, use native UUIDs

**Steps:**
1. Set `DATABASE_URL=postgresql://...` in `.env.production`
2. Run `alembic upgrade head` (or apply `db/migrations/*.sql` in order)
3. Migrate data: `pg_restore` or `sqlite3` → `pg_dump` via `pgloader`
4. Remove FTS5 code from `search/sync.py` and `search/fts.py`; FAISS covers semantic search

**Estimated effort:** 1–2 days.
