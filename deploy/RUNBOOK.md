# Deployment Runbook — Research Intelligence Platform
## Vercel (frontend) + Cloudflare Tunnel (backend exposure) + Local Mac (FastAPI)

Work through each step in order. Every step has a verification command.

---

## Architecture

```
Browser
  │
  ├─── HTTPS ──► Vercel CDN ──► Next.js (pre-built static bundle)
  │                                │
  │                                │  NEXT_PUBLIC_API_URL (baked at build time)
  │                                ▼
  └─── HTTPS ──► Cloudflare Edge ──► cloudflared daemon ──► localhost:8000
                                                                │
                                                         FastAPI (uvicorn)
                                                           ├── SQLite DB (local file)
                                                           ├── FAISS index (local file)
                                                           └── LLM proxy (corporate network)
```

**Key constraints:**
- `NEXT_PUBLIC_API_URL` is baked into the Vercel build — changing the tunnel URL requires a Vercel redeploy.
- The LLM proxy (`clear-llm-proxy.internal.cleartax.co`) is only reachable on the corporate office network. The Mac must stay on that network while the demo runs.
- The Mac must not sleep. System Preferences → Battery → disable "Prevent automatic sleeping" and enable "Wake for network access."

---

## Prerequisites

| Item | Required | Notes |
|------|----------|-------|
| Mac on corporate office network | Yes | LLM proxy at `10.1.x.x` only reachable here |
| `research_platform.db` in repo root | Yes | SQLite, WAL mode enabled |
| `embeddings.index` + `embeddings_ids.json` in repo root | Yes | FAISS index |
| Python venv with dependencies | Yes | `source .venv/bin/activate` |
| Cloudflare account + domain | Yes | Free tier sufficient |
| `cloudflared` installed | Yes | `brew install cloudflare/cloudflare/cloudflared` |
| Vercel account | Yes | Free tier sufficient |
| Vercel CLI | Yes | `npm i -g vercel` |

---

## Step 1 — Configure .env

```bash
cp .env.example .env
```

Edit `.env` and set:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `sqlite:///research_platform.db` |
| `LLM_PROVIDER` | `anthropic` |
| `ANTHROPIC_API_KEY` | your key (issued by the proxy) |
| `ANTHROPIC_BASE_URL` | `https://clear-llm-proxy.internal.cleartax.co` |
| `CORS_ORIGIN` | your Vercel URL — set **after** Step 3 |
| `NEXT_PUBLIC_API_URL` | your tunnel URL — set **after** Step 2 |
| `SEMANTIC_SEARCH` | `true` |

Leave `CORS_ORIGIN` and `NEXT_PUBLIC_API_URL` blank for now — you'll fill them in after getting the URLs in steps 2 and 3.

---

## Step 2 — Set up Cloudflare Tunnel

Follow `deploy/cloudflare-tunnel/README.md` for full instructions.

**Quick version (stable tunnel):**

```bash
# Install
brew install cloudflare/cloudflare/cloudflared

# Authenticate
cloudflared login

# Create tunnel
cloudflared tunnel create rip-backend

# Copy and edit config
cp deploy/cloudflare-tunnel/config.yml.example ~/.cloudflared/config.yml
# Edit: replace YOUR_TUNNEL_ID and api.yourdomain.com

# Create DNS record
cloudflared tunnel route dns rip-backend api.yourdomain.com

# Install as a persistent service (survives reboots)
sudo cloudflared service install
sudo launchctl start com.cloudflare.cloudflared
```

Set Cloudflare proxy timeout:
- Dashboard → your domain → **Network** → **Proxy Read Timeout** → **300 seconds**

Your tunnel URL is `https://api.yourdomain.com`.

**Update `.env`:**
```
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
```

---

## Step 3 — Deploy frontend to Vercel

```bash
cd apps/web

# First deploy — Vercel will ask for project name and settings
# Framework: Next.js (auto-detected)
# Root directory: apps/web (already cd'd there)
# Build command: next build (default)
# Output: .next (default)
vercel --prod
```

After the first deploy, Vercel shows your URL (e.g. `https://your-project.vercel.app`).

**Set environment variables in Vercel:**

```bash
vercel env add NEXT_PUBLIC_API_URL production
# Enter: https://api.yourdomain.com/api/v1

vercel env add NEXT_PUBLIC_API_URL preview
# Enter: https://api.yourdomain.com/api/v1
```

**Update `.env` with CORS origin:**
```
CORS_ORIGIN=https://your-project.vercel.app
```

**Redeploy with all env vars baked in:**
```bash
vercel --prod
```

Verify the deployed frontend loads:
```bash
curl -sf https://your-project.vercel.app | grep -o '<title>.*</title>'
# Expected: <title>InsightEngine — AI Research Hub</title>
```

---

## Step 4 — Start the backend

```bash
# From repo root, with venv activated
source .venv/bin/activate
bash deploy/start-backend.sh
```

Expected output:
```
Starting backend...
  Log:  /path/to/research-intelligence-platfrom/backend.log
  Env:  CORS_ORIGIN=https://your-project.vercel.app
  LLM:  anthropic  proxy=https://clear-llm-proxy.internal.cleartax.co
...
Backend started (PID 12345)
Waiting for /health...... OK
Backend is healthy.
```

If the wait times out, check the log:
```bash
tail -50 backend.log
```

---

## Step 5 — Run the health check

```bash
# Pass your tunnel URL as the first argument
CORS_ORIGIN=https://your-project.vercel.app \
  bash deploy/healthcheck.sh https://api.yourdomain.com
```

Expected output:
```
── Local backend (http://127.0.0.1:8000) ──────────────────────────────────
  ✓  /health → ok, db connected
  ✓  /api/v1/stats → 2510 papers
  ✓  /api/v1/search (keyword) → HTTP 200
  ✓  CORS header present for https://your-project.vercel.app
  …  /api/v1/chat (LLM call, up to 30s)
  ✓  /api/v1/chat → answer received

── Cloudflare Tunnel (https://api.yourdomain.com) ─────────────────────────
  ✓  tunnel /health → HTTP 200
  ✓  tunnel /api/v1/stats → HTTP 200
  ✓  tunnel /api/v1/search → HTTP 200

── Summary ───────────────────────────────────────────────────────────────
  Passed: 8   Failed: 0
  All checks passed.
```

---

## Step 6 — Open the demo URL

Navigate to `https://your-project.vercel.app` in a browser.

Verify:
- [ ] Page loads (no blank screen)
- [ ] No "Backend unavailable" red banner at the top
- [ ] Dashboard shows paper counts
- [ ] Search returns results
- [ ] Chat responds (will take 10–20s)
- [ ] Feature Mapper returns results for a >50-word input (will take 55–115s)

---

## Day-of-demo checklist

Run this before every demo session:

```bash
# 1. Confirm Mac is on the corporate office network
curl -sf https://clear-llm-proxy.internal.cleartax.co/health 2>/dev/null \
  && echo "Proxy reachable" || echo "WARNING: proxy not reachable — chat will fail"

# 2. Confirm backend is running
curl -sf http://127.0.0.1:8000/health || bash deploy/start-backend.sh

# 3. Confirm tunnel is up
curl -sf https://api.yourdomain.com/health

# 4. Confirm Mac won't sleep
# System Preferences → Battery → Power Adapter → uncheck "Prevent automatic sleeping"
# (or run: sudo pmset -a sleep 0)
```

---

## Stopping the backend

```bash
bash deploy/stop-backend.sh
```

To also stop the tunnel service:
```bash
sudo launchctl stop com.cloudflare.cloudflared
```

---

## Redeploying the frontend

Required when: Vercel URL changes, tunnel URL changes, or frontend code changes.

```bash
cd apps/web
vercel --prod
```

If the tunnel URL changed, update the Vercel env var first:
```bash
vercel env rm NEXT_PUBLIC_API_URL production
vercel env add NEXT_PUBLIC_API_URL production
# Enter new URL
vercel --prod
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Red "Backend unavailable" banner | Backend not running or tunnel down | `bash deploy/start-backend.sh` ; check `cloudflared tunnel list` |
| Chat/search returns CORS error | `CORS_ORIGIN` doesn't match Vercel URL | Check `.env` `CORS_ORIGIN`, restart backend |
| Feature Mapper returns 504 | Cloudflare proxy timeout too short | Dashboard → Network → Proxy Read Timeout → 300s |
| Feature Mapper returns 422 | Input text < 50 words | Tell the user to paste a longer document |
| Chat returns "LLM unavailable" | Off corporate network or proxy down | Connect to office network; check `ANTHROPIC_BASE_URL` |
| Vercel shows old API URL | `NEXT_PUBLIC_API_URL` not set before build | Set env var in Vercel dashboard, redeploy |
| Backend log: "database is locked" | SQLite not in WAL mode | `python3 -c "import sqlite3; c=sqlite3.connect('research_platform.db'); c.execute('PRAGMA journal_mode=WAL')"` |

---

## Known limitations

| Limitation | Impact |
|------------|--------|
| Mac must stay awake on corporate network | Demo unavailable if lid closed or network drops |
| No zero-downtime restarts | In-flight requests drop when backend restarts |
| SQLite single-writer | Fine for <20 concurrent users; upgrade to PostgreSQL for production |
| Feature Mapper: 55–115s per request | Normal; Cloudflare timeout set to 300s covers it |
| `NEXT_PUBLIC_API_URL` baked at build time | Changing the tunnel URL requires a Vercel redeploy |
