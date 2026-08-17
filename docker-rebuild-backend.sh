#!/usr/bin/env bash
# Rebuild and restart only the backend container (picks up API code changes).
#
#   ./docker-rebuild-backend.sh
set -euo pipefail

cd "$(dirname "$0")"
./docker compose up -d --build backend

echo ""
echo "Backend rebuilt. Check health:"
echo "  curl http://localhost:8000/api/health"
