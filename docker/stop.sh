#!/usr/bin/env bash
# Stop all NoobBook and Supabase containers gracefully.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "Docker Compose not found"; exit 1
fi

echo "Stopping NoobBook..."
$COMPOSE -f "$ROOT_DIR/docker-compose.yml" down 2>/dev/null || true

echo "Stopping Supabase..."
$COMPOSE -f "$SCRIPT_DIR/supabase/docker-compose.yml" down 2>/dev/null || true

echo "All services stopped."
