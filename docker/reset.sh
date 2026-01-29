#!/usr/bin/env bash
# Reset NoobBook Docker setup — stops all containers and optionally deletes volumes.
#
# Usage:
#   bash docker/reset.sh        # Stop containers, keep data
#   bash docker/reset.sh -v     # Stop containers AND delete all data volumes

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

DELETE_VOLUMES=false
if [[ "${1:-}" == "-v" ]]; then
    DELETE_VOLUMES=true
fi

if $DELETE_VOLUMES; then
    echo "WARNING: This will delete ALL NoobBook data (database, uploads, storage)."
    read -rp "Are you sure? Type 'yes' to confirm: " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

echo "Stopping NoobBook containers..."
$COMPOSE -f "$ROOT_DIR/docker-compose.yml" down --remove-orphans 2>/dev/null || true

echo "Stopping Supabase containers..."
if $DELETE_VOLUMES; then
    $COMPOSE -f "$SCRIPT_DIR/supabase/docker-compose.yml" down -v --remove-orphans 2>/dev/null || true
    # Remove the NoobBook backend data volume
    docker volume rm noobbook-backend-data 2>/dev/null || true
    # Remove local Supabase volume data (db data, storage)
    rm -rf "$SCRIPT_DIR/supabase/volumes/db/data"
    rm -rf "$SCRIPT_DIR/supabase/volumes/storage"
    echo "All volumes deleted."
else
    $COMPOSE -f "$SCRIPT_DIR/supabase/docker-compose.yml" down --remove-orphans 2>/dev/null || true
fi

# Remove the shared network
docker network rm noobbook-network 2>/dev/null || true

# Remove generated .env files if doing a full reset
if $DELETE_VOLUMES; then
    rm -f "$SCRIPT_DIR/.env"
    rm -f "$SCRIPT_DIR/supabase/.env"
    echo "Generated .env files removed."
fi

echo "Reset complete."
