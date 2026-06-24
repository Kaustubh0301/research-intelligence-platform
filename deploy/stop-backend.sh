#!/usr/bin/env bash
# Stop the backend started by start-backend.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$REPO_ROOT/backend.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file found — backend may not be running."
  exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  rm -f "$PID_FILE"
  echo "Backend stopped (PID $PID)."
else
  echo "Process $PID not running; cleaning up PID file."
  rm -f "$PID_FILE"
fi
