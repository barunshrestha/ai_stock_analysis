#!/usr/bin/env bash
# Local dev alongside Docker — hot reload without rebuilding containers.
#
#   Docker (always-on) : http://localhost:3002  backend :8000  postgres :5432
#   Local dev          : http://localhost:3003  backend :8001
#
# One command:  ./start_dev_local.sh
# Ctrl+C stops local servers only; Docker keeps running.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env.dev-local ]; then
  echo "Missing .env.dev-local — see .env.example or README_DEPLOYMENT.md" >&2
  exit 1
fi

if [ ! -f frontend/.env.local ]; then
  cp frontend/.env.local.example frontend/.env.local
  echo "Created frontend/.env.local"
fi

# Ensure local dev points at :8001, not Docker :8000
if ! grep -q 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8001' frontend/.env.local 2>/dev/null; then
  if grep -q '^NEXT_PUBLIC_API_URL=' frontend/.env.local 2>/dev/null; then
    sed -i '' 's|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=http://127.0.0.1:8001|' frontend/.env.local
  else
    echo 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8001' >> frontend/.env.local
  fi
  echo "Set frontend/.env.local → http://127.0.0.1:8001 (local backend, not Docker :8000)"
fi

set -a
if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
else
  echo "Warning: no .env — copy .env.example and set DATABASE_URL" >&2
fi
# shellcheck disable=SC1091
source .env.dev-local
set +a

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set. Add it to .env (e.g. postgresql://user:pass@localhost:5432/stock_analysis)" >&2
  exit 1
fi

if [ ! -x venv/bin/python ]; then
  echo "venv not found — create it first: python3 -m venv venv && ./venv/bin/pip install -e ." >&2
  exit 1
fi

stop_stale_local_dev() {
  local pid port
  for port in 8001 3003; do
    for pid in $(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null); do
      echo "Stopping stale process on port $port (PID $pid)..."
      kill "$pid" 2>/dev/null || true
    done
  done
  sleep 1
  for port in 8001 3003; do
    for pid in $(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null); do
      kill -9 "$pid" 2>/dev/null || true
    done
  done
  sleep 0.5
}

stop_stale_local_dev

echo "Starting local dev (Docker can stay running on :8000 and :3002)..."
echo "  Frontend  http://localhost:3003"
echo "  Backend   http://127.0.0.1:8001"
echo ""

./venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

cd frontend
npm run dev:local
