#!/usr/bin/env bash
# Verify the full deployment stack is healthy.
# Usage:
#   bash deploy/healthcheck.sh                        # local backend only
#   bash deploy/healthcheck.sh https://api.yourdomain.com   # tunnel URL
set -euo pipefail

LOCAL="http://127.0.0.1:8000"
REMOTE="${1:-}"

PASS=0
FAIL=0

ok()   { echo "  ✓  $*"; ((PASS++)) || true; }
fail() { echo "  ✗  $*"; ((FAIL++)) || true; }
hdr()  { echo ""; echo "── $* ──────────────────────────────────────"; }

check_endpoint() {
  local label="$1"
  local url="$2"
  local method="${3:-GET}"
  local data="${4:-}"
  local expect="${5:-200}"

  if [[ "$method" == "POST" ]]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
      -H "Content-Type: application/json" \
      --max-time 30 \
      -d "$data" "$url" 2>/dev/null || echo "000")
  else
    status=$(curl -s -o /dev/null -w "%{http_code}" \
      --max-time 30 "$url" 2>/dev/null || echo "000")
  fi

  if [[ "$status" == "$expect" ]]; then
    ok "$label → HTTP $status"
  else
    fail "$label → HTTP $status (expected $expect)"
  fi
}

# ── Local backend ─────────────────────────────────────────────────────────────
hdr "Local backend ($LOCAL)"

# Health
HEALTH=$(curl -sf --max-time 5 "$LOCAL/health" 2>/dev/null || echo '{}')
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  ok "/health → ok, db connected"
else
  fail "/health → $HEALTH"
fi

# Stats (verifies DB is readable and has data)
STATS=$(curl -sf --max-time 5 "$LOCAL/api/v1/stats" 2>/dev/null || echo '{}')
PAPERS=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_papers',0))" 2>/dev/null || echo 0)
if [[ "$PAPERS" -gt 0 ]]; then
  ok "/api/v1/stats → $PAPERS papers"
else
  fail "/api/v1/stats → no papers returned"
fi

# Search (verifies FTS + FAISS)
check_endpoint "/api/v1/search (keyword)" \
  "$LOCAL/api/v1/search" POST \
  '{"query":"transformer","limit":3}' 200

# Chat (verifies LLM proxy reachability — times out up to 30s)
echo "  …  /api/v1/chat (LLM call, up to 30s)"
CHAT=$(curl -sf --max-time 30 -X POST \
  -H "Content-Type: application/json" \
  -d '{"message":"What is LoRA?","history":[]}' \
  "$LOCAL/api/v1/chat" 2>/dev/null || echo '{}')
if echo "$CHAT" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('answer') else 1)" 2>/dev/null; then
  ok "/api/v1/chat → answer received"
else
  fail "/api/v1/chat → no answer (proxy unreachable or key invalid)"
fi

# CORS header present when CORS_ORIGIN is set
if [[ -n "${CORS_ORIGIN:-}" ]]; then
  CORS_HEADER=$(curl -s --max-time 5 \
    -H "Origin: $CORS_ORIGIN" \
    -I "$LOCAL/health" 2>/dev/null | grep -i "access-control-allow-origin" || echo "")
  if echo "$CORS_HEADER" | grep -q "$CORS_ORIGIN"; then
    ok "CORS header present for $CORS_ORIGIN"
  else
    fail "CORS header missing for $CORS_ORIGIN — check CORS_ORIGIN env var"
  fi
fi

# ── Cloudflare Tunnel ─────────────────────────────────────────────────────────
if [[ -n "$REMOTE" ]]; then
  hdr "Cloudflare Tunnel ($REMOTE)"
  check_endpoint "tunnel /health"       "$REMOTE/health"           GET "" 200
  check_endpoint "tunnel /api/v1/stats" "$REMOTE/api/v1/stats"     GET "" 200
  check_endpoint "tunnel /api/v1/search" "$REMOTE/api/v1/search"   POST \
    '{"query":"LoRA","limit":2}' 200
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "── Summary ──────────────────────────────────────────────────────────"
echo "  Passed: $PASS   Failed: $FAIL"
if [[ $FAIL -eq 0 ]]; then
  echo "  All checks passed."
  exit 0
else
  echo "  Some checks failed — see above."
  exit 1
fi
