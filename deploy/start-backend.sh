#!/usr/bin/env bash
# Start the Research Intelligence Platform FastAPI backend.
# Run from the repository root: bash deploy/start-backend.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_ROOT/backend.log"
PID_FILE="$REPO_ROOT/backend.pid"

# ── Already running? ──────────────────────────────────────────────────────────
if [[ -f "$PID_FILE" ]]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Backend already running (PID $OLD_PID). To restart: bash deploy/stop-backend.sh"
    exit 0
  else
    echo "Stale PID file found; cleaning up."
    rm -f "$PID_FILE"
  fi
fi

# ── Preflight checks ──────────────────────────────────────────────────────────
cd "$REPO_ROOT"

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in values."
  exit 1
fi

if [[ ! -f "research_platform.db" ]]; then
  echo "ERROR: research_platform.db not found in $REPO_ROOT"
  exit 1
fi

if [[ ! -f "embeddings.index" ]]; then
  echo "ERROR: embeddings.index not found in $REPO_ROOT"
  exit 1
fi

if ! python3 -c "import uvicorn" 2>/dev/null; then
  echo "ERROR: uvicorn not found. Activate your venv: source .venv/bin/activate"
  exit 1
fi

# ── Load env ──────────────────────────────────────────────────────────────────
set -a
# shellcheck disable=SC1091
source .env
set +a

# ── Start ─────────────────────────────────────────────────────────────────────
echo "Starting backend..."
echo "  Log:  $LOG_FILE"
echo "  Env:  CORS_ORIGIN=${CORS_ORIGIN:-<not set — localhost only>}"
echo "  LLM:  ${LLM_PROVIDER:-anthropic}  proxy=${ANTHROPIC_BASE_URL:-api.anthropic.com}"
echo ""

nohup python3 -m uvicorn api.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 2 \
  --timeout-keep-alive 75 \
  > "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "Backend started (PID $(cat "$PID_FILE"))"

# ── Wait for healthy ──────────────────────────────────────────────────────────
echo -n "Waiting for /health"
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo " OK"
    echo "Backend is healthy. Logs: tail -f $LOG_FILE"
    exit 0
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "WARNING: Backend did not become healthy after 30s. Check: tail -50 $LOG_FILE"
exit 1
