#!/usr/bin/env bash
# =============================================================================
# NoobBook Docker Setup — one command to start everything.
#
# Usage:
#   bash docker/setup.sh
#
# What it does:
#   1. Checks prerequisites (Docker, Docker Compose)
#   2. Generates Supabase secrets (JWT, passwords, tokens)
#   3. Creates .env files from templates
#   4. Creates the shared Docker network
#   5. Starts Supabase
#   6. Waits for Kong (API gateway) to become healthy
#   7. Builds and starts NoobBook (backend + frontend + migration)
#   8. Prints access URLs
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---- Step 1: Prerequisites ----
info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || error "Docker is not installed. See https://docs.docker.com/get-docker/"

# Check for docker compose (v2 plugin or standalone docker-compose)
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    error "Docker Compose is not installed. See https://docs.docker.com/compose/install/"
fi

success "Docker and Docker Compose found ($COMPOSE)"

# ---- Step 2: Generate secrets ----
generate_password() {
    openssl rand -base64 32 | tr -d '/+=' | head -c 40
}

generate_hex() {
    openssl rand -hex "$1"
}

# Portable in-place env var replacement (works on both macOS and Linux).
# Replaces lines like KEY=anything with KEY=new_value, preserving values
# that contain special characters (=, /, +).
replace_env_var() {
    local file="$1" key="$2" value="$3"
    local tmp="${file}.tmp"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "${key}="* ]]; then
            echo "${key}=${value}"
        else
            echo "$line"
        fi
    done < "$file" > "$tmp"
    mv "$tmp" "$file"
}

generate_jwt() {
    local role="$1"
    local secret="$2"
    # JWT header and payload
    local header='{"alg":"HS256","typ":"JWT"}'
    local payload="{\"role\":\"${role}\",\"iss\":\"supabase\",\"iat\":1641769200,\"exp\":1799535600}"

    local header_b64
    header_b64=$(echo -n "$header" | openssl base64 -A | tr '+/' '-_' | tr -d '=')
    local payload_b64
    payload_b64=$(echo -n "$payload" | openssl base64 -A | tr '+/' '-_' | tr -d '=')

    local signature
    signature=$(echo -n "${header_b64}.${payload_b64}" | openssl dgst -sha256 -hmac "$secret" -binary | openssl base64 -A | tr '+/' '-_' | tr -d '=')

    echo "${header_b64}.${payload_b64}.${signature}"
}

# ---- Step 3: Create .env files ----
SUPABASE_ENV="$SCRIPT_DIR/supabase/.env"
NOOBBOOK_ENV="$SCRIPT_DIR/.env"

# Generate Supabase secrets if .env doesn't exist yet
if [ ! -f "$SUPABASE_ENV" ]; then
    info "Generating Supabase secrets..."
    POSTGRES_PASSWORD=$(generate_password)
    JWT_SECRET=$(generate_hex 32)
    SECRET_KEY_BASE=$(generate_hex 48)
    VAULT_ENC_KEY=$(generate_hex 16)
    PG_META_CRYPTO_KEY=$(generate_hex 16)
    DASHBOARD_PASSWORD=$(generate_password)
    LOGFLARE_PUBLIC=$(generate_hex 24)
    LOGFLARE_PRIVATE=$(generate_hex 24)
    POOLER_TENANT_ID=$(generate_hex 8)

    ANON_KEY=$(generate_jwt "anon" "$JWT_SECRET")
    SERVICE_ROLE_KEY=$(generate_jwt "service_role" "$JWT_SECRET")

    # Write Supabase .env from template with generated values
    cp "$SCRIPT_DIR/supabase/.env.example" "$SUPABASE_ENV"

    # Replace placeholder values with generated secrets (portable across macOS and Linux)
    replace_env_var "$SUPABASE_ENV" "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
    replace_env_var "$SUPABASE_ENV" "JWT_SECRET" "$JWT_SECRET"
    replace_env_var "$SUPABASE_ENV" "ANON_KEY" "$ANON_KEY"
    replace_env_var "$SUPABASE_ENV" "SERVICE_ROLE_KEY" "$SERVICE_ROLE_KEY"
    replace_env_var "$SUPABASE_ENV" "DASHBOARD_PASSWORD" "$DASHBOARD_PASSWORD"
    replace_env_var "$SUPABASE_ENV" "SECRET_KEY_BASE" "$SECRET_KEY_BASE"
    replace_env_var "$SUPABASE_ENV" "VAULT_ENC_KEY" "$VAULT_ENC_KEY"
    replace_env_var "$SUPABASE_ENV" "PG_META_CRYPTO_KEY" "$PG_META_CRYPTO_KEY"
    replace_env_var "$SUPABASE_ENV" "LOGFLARE_PUBLIC_ACCESS_TOKEN" "$LOGFLARE_PUBLIC"
    replace_env_var "$SUPABASE_ENV" "LOGFLARE_PRIVATE_ACCESS_TOKEN" "$LOGFLARE_PRIVATE"
    replace_env_var "$SUPABASE_ENV" "POOLER_TENANT_ID" "$POOLER_TENANT_ID"

    success "Supabase .env created with generated secrets"
else
    info "Supabase .env already exists, reading existing values..."
    # shellcheck disable=SC1090
    source "$SUPABASE_ENV"
    ANON_KEY="${ANON_KEY}"
    SERVICE_ROLE_KEY="${SERVICE_ROLE_KEY}"
    POSTGRES_PASSWORD="${POSTGRES_PASSWORD}"
fi

# Create NoobBook .env if it doesn't exist
if [ ! -f "$NOOBBOOK_ENV" ]; then
    info "Creating NoobBook .env from template..."
    cp "$SCRIPT_DIR/.env.example" "$NOOBBOOK_ENV"

    # Source Supabase env to get generated keys
    # shellcheck disable=SC1090
    source "$SUPABASE_ENV"

    replace_env_var "$NOOBBOOK_ENV" "SUPABASE_ANON_KEY" "$ANON_KEY"
    replace_env_var "$NOOBBOOK_ENV" "SUPABASE_SERVICE_KEY" "$SERVICE_ROLE_KEY"
    replace_env_var "$NOOBBOOK_ENV" "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
    replace_env_var "$NOOBBOOK_ENV" "SECRET_KEY" "$(generate_password)"

    success "NoobBook .env created"

    # Prompt for API keys if they're empty
    # shellcheck disable=SC1090
    source "$NOOBBOOK_ENV"
    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        warn "ANTHROPIC_API_KEY is not set in docker/.env"
        warn "Edit docker/.env and add your API keys before the app will work."
    fi
else
    info "NoobBook .env already exists, skipping..."
fi

# ---- Step 4: Create Docker network ----
if ! docker network inspect noobbook-network >/dev/null 2>&1; then
    info "Creating Docker network: noobbook-network"
    docker network create noobbook-network
    success "Network created"
else
    info "Docker network noobbook-network already exists"
fi

# ---- Step 5: Start Supabase ----
info "Starting Supabase services..."
$COMPOSE -f "$SCRIPT_DIR/supabase/docker-compose.yml" --env-file "$SUPABASE_ENV" up -d

# ---- Step 6: Wait for Kong health ----
info "Waiting for Supabase API gateway (Kong) to become healthy..."
KONG_PORT=$(grep '^KONG_HTTP_PORT=' "$SUPABASE_ENV" | cut -d= -f2)
KONG_PORT="${KONG_PORT:-8000}"

TIMEOUT=120
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    if docker exec supabase-kong kong health >/dev/null 2>&1; then
        success "Supabase is healthy"
        break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    printf "."
done
echo ""

if [ $ELAPSED -ge $TIMEOUT ]; then
    error "Supabase did not become healthy within ${TIMEOUT}s. Check: docker logs supabase-kong"
fi

# ---- Step 7: Build and start NoobBook ----
info "Building and starting NoobBook..."
$COMPOSE -f "$ROOT_DIR/docker-compose.yml" --env-file "$NOOBBOOK_ENV" up -d --build

# ---- Step 8: Wait for migration ----
info "Waiting for database migration to complete..."
$COMPOSE -f "$ROOT_DIR/docker-compose.yml" --env-file "$NOOBBOOK_ENV" logs -f migrate 2>&1 | while read -r line; do
    echo "  $line"
    if echo "$line" | grep -q "Migration complete"; then
        break
    fi
    if echo "$line" | grep -q "exited with code"; then
        break
    fi
done

# ---- Step 9: Print summary ----
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  NoobBook is running!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  App:              ${CYAN}http://localhost${NC}"
echo -e "  Backend API:      ${CYAN}http://localhost:5001/api/v1${NC}"
echo -e "  Supabase API:     ${CYAN}http://localhost:8000${NC}"
echo ""
echo -e "  Stop:   ${YELLOW}bash docker/stop.sh${NC}"
echo -e "  Reset:  ${YELLOW}bash docker/reset.sh${NC}"
echo ""
if grep -q '^ANTHROPIC_API_KEY=$' "$NOOBBOOK_ENV" 2>/dev/null; then
    echo -e "${YELLOW}  Remember to add your API keys to docker/.env${NC}"
    echo ""
fi
