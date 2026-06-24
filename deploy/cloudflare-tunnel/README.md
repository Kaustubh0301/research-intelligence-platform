# Cloudflare Tunnel Setup — Research Intelligence Platform

Exposes the local FastAPI backend (localhost:8000) at a stable public HTTPS URL.
No inbound ports opened on your Mac.

## Prerequisites

- Cloudflare account (free)
- A domain managed by Cloudflare DNS (or use the Quick Start below for a temporary URL)

---

## Option A — Quick start (no domain, temporary URL)

Use this to get a public URL in under 60 seconds. The URL changes every restart.

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel --url http://localhost:8000
```

The terminal prints a URL like `https://random-words.trycloudflare.com`.
Use this as `NEXT_PUBLIC_API_URL` when deploying to Vercel (you must redeploy Vercel each time the URL changes).

---

## Option B — Stable URL (your own domain, recommended for demo)

### Step 1 — Install cloudflared

```bash
brew install cloudflare/cloudflare/cloudflared
```

### Step 2 — Log in to Cloudflare

```bash
cloudflared login
# Opens browser; select your domain zone
```

### Step 3 — Create the tunnel

```bash
cloudflared tunnel create rip-backend
# Prints: Created tunnel rip-backend with id <TUNNEL_ID>
# Credentials saved to ~/.cloudflared/<TUNNEL_ID>.json
```

### Step 4 — Write the config file

Copy the template in this directory:

```bash
cp deploy/cloudflare-tunnel/config.yml.example ~/.cloudflared/config.yml
```

Edit `~/.cloudflared/config.yml` and replace:
- `YOUR_TUNNEL_ID` — the UUID from step 3
- `api.yourdomain.com` — your chosen subdomain

### Step 5 — Route DNS

```bash
cloudflared tunnel route dns rip-backend api.yourdomain.com
# Cloudflare creates a CNAME pointing api.yourdomain.com → <TUNNEL_ID>.cfargotunnel.com
```

Verify in the Cloudflare dashboard: DNS → should see the CNAME record.

### Step 6 — Set Cloudflare proxy read timeout

Feature Mapper requests take 55–115 seconds. The default Cloudflare proxy timeout is 100s.

Cloudflare dashboard → your domain → **Network** → **Proxy Read Timeout** → set to **300 seconds**.

### Step 7 — Run as a background daemon (survives reboots)

```bash
sudo cloudflared service install
sudo launchctl start com.cloudflare.cloudflared
```

Verify:
```bash
cloudflared tunnel info rip-backend
curl -sf https://api.yourdomain.com/health
# Expected: {"status":"ok","db":"connected"}
```

### Step 8 — Set environment variables

In your `.env` file:
```
CORS_ORIGIN=https://your-project.vercel.app
ANTHROPIC_BASE_URL=https://your-proxy.example.com
```

Set `ANTHROPIC_BASE_URL` to your LiteLLM-compatible proxy URL, or leave it blank to use
`api.anthropic.com` directly. The FastAPI process reads this from the environment at startup.

---

## Stopping the tunnel

```bash
# If running as a service:
sudo launchctl stop com.cloudflare.cloudflared

# If running manually:
# Ctrl-C in the terminal where cloudflared is running
```

## Checking tunnel status

```bash
cloudflared tunnel list
cloudflared tunnel info rip-backend
```

---

## Cloudflare Access (optional but recommended)

Add an email OTP gate so only approved users can reach the API:

1. Cloudflare dashboard → **Zero Trust** → **Access** → **Applications** → **Add**
2. Type: **Self-hosted**
3. Domain: `api.yourdomain.com`
4. Policy: **Email** → include the email addresses of your demo users
5. Save

Users see a one-time email verification before accessing the API.
No code changes needed — Cloudflare handles auth at the edge.
