#!/usr/bin/env bash
# Start the full stack in Docker (background, auto-restart on crash/reboot).
#
#   Frontend : http://localhost:3002
#   Backend  : http://localhost:8000  (docs at /docs)
#   Postgres : localhost:5432
#
# Stop and free ports:  ./docker compose down
# Logs:                 ./docker compose logs -f
set -euo pipefail

cd "$(dirname "$0")"

# shellcheck source=scripts/resolve-docker.sh
source "$(dirname "$0")/scripts/resolve-docker.sh"

if ! require_docker; then
  exit 1
fi

# Free ports used by ./start_dev.sh so Docker can bind 8000 and 3002.
stop_local_dev() {
  local pid
  for pid in $(lsof -ti tcp:3002 -sTCP:LISTEN 2>/dev/null); do
    if ! docker ps -q 2>/dev/null | xargs -I{} docker inspect -f '{{.State.Pid}}' {} 2>/dev/null | grep -qx "$pid"; then
      echo "Stopping local process on port 3002 (PID $pid)..."
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in $(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null); do
    # Skip if owned by Docker Desktop
    case "$(ps -p "$pid" -o comm= 2>/dev/null)" in
      com.docker.*|docker*|Docker*) continue ;;
    esac
    echo "Stopping local process on port 8000 (PID $pid)..."
    kill "$pid" 2>/dev/null || true
  done
  sleep 1
}

stop_local_dev

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "No .env found — copying .env.example to .env"
    cp .env.example .env
  else
    echo "Create a .env file first (see .env.example)." >&2
    exit 1
  fi
fi

echo "Building and starting containers (detached)..."
docker compose up -d --build

echo ""
echo "Waiting for backend health..."
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "Backend is healthy."
    break
  fi
  sleep 2
done

echo ""
echo "Stock Analysis is running:"
echo "  Frontend  http://localhost:3002"
echo "  Backend   http://localhost:8000"
echo "  API docs  http://localhost:8000/docs"
echo ""
echo "Commands:"
echo "  ./docker compose ps          # status"
echo "  ./docker compose logs -f     # live logs"
echo "  ./docker compose down        # stop and free ports"
echo "  ./docker-rebuild-backend.sh  # rebuild backend only"
