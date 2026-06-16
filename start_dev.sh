#!/usr/bin/env bash
# Start both dev servers for local development.
#   Backend  : http://localhost:8000  (FastAPI, auto-reload)
#   Frontend : http://localhost:3002  (Next.js)
# Ctrl+C stops both.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x venv/bin/python ]; then
  echo "venv not found — create it first: python3 -m venv venv && ./venv/bin/pip install -e ." >&2
  exit 1
fi

./venv/bin/python -m uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

cd frontend
npm run dev
