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
#   5. Creates edge functions placeholder (prevents container crash)
#   6. Starts Supabase
#   7. Waits for Kong (API gateway) to become healthy
#   8. Creates MinIO storage bucket (for macOS compatibility)
#   9. Builds and starts NoobBook (backend + frontend + migration)
#   10. Waits for database migration
#   11. Prints access URLs
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
    # Use Python for JWT generation — macOS LibreSSL's openssl dgst -hmac -binary
    # can segfault (exit 139) on certain versions.
    python3 -c "
import hmac, hashlib, base64, json

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

header = json.dumps({'alg':'HS256','typ':'JWT'}, separators=(',',':')).encode()
payload = json.dumps({'role':'${role}','iss':'supabase','iat':1641769200,'exp':1799535600}, separators=(',',':')).encode()

h = b64url(header)
p = b64url(payload)
sig = hmac.new('${secret}'.encode(), f'{h}.{p}'.encode(), hashlib.sha256).digest()

print(f'{h}.{p}.{b64url(sig)}')
"
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
    info "NoobBook .env already exists, ensuring Supabase keys are set..."
    # shellcheck disable=SC1090
    source "$SUPABASE_ENV"
    # Inject each Supabase-managed key independently (user may have set some but not others)
    INJECTED=false
    if grep -q '^SUPABASE_ANON_KEY=$' "$NOOBBOOK_ENV" 2>/dev/null; then
        replace_env_var "$NOOBBOOK_ENV" "SUPABASE_ANON_KEY" "$ANON_KEY"
        INJECTED=true
    fi
    if grep -q '^SUPABASE_SERVICE_KEY=$' "$NOOBBOOK_ENV" 2>/dev/null; then
        replace_env_var "$NOOBBOOK_ENV" "SUPABASE_SERVICE_KEY" "$SERVICE_ROLE_KEY"
        INJECTED=true
    fi
    if grep -q '^POSTGRES_PASSWORD=$' "$NOOBBOOK_ENV" 2>/dev/null; then
        replace_env_var "$NOOBBOOK_ENV" "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
        INJECTED=true
    fi
    if [ "$INJECTED" = true ]; then
        success "Supabase keys injected into existing .env"
    fi
fi

# ---- Step 4: Create Docker network ----
if ! docker network inspect noobbook-network >/dev/null 2>&1; then
    info "Creating Docker network: noobbook-network"
    docker network create noobbook-network
    success "Network created"
else
    info "Docker network noobbook-network already exists"
fi

# ---- Step 5: Create edge functions placeholder ----
# This prevents the edge-functions container from crashing on startup
FUNCTIONS_DIR="$SCRIPT_DIR/supabase/volumes/functions/main"
if [ ! -f "$FUNCTIONS_DIR/index.ts" ]; then
    info "Creating edge functions placeholder..."
    mkdir -p "$FUNCTIONS_DIR"
    cat > "$FUNCTIONS_DIR/index.ts" << 'EOF'
// Placeholder edge function - not used by NoobBook
// This file exists to prevent the edge-functions container from crashing

Deno.serve(() => new Response("Edge Functions not used by NoobBook"));
EOF
    success "Edge functions placeholder created"
fi

# ---- Step 6: Start Supabase ----
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

# ---- Step 8: Create MinIO storage bucket ----
# macOS Docker doesn't support xattr, so we use MinIO for S3-compatible storage
info "Creating MinIO storage bucket..."
sleep 5  # Wait for MinIO to be fully ready
if docker exec supabase-minio mc alias set local http://localhost:9000 supabase supabase123 >/dev/null 2>&1; then
    docker exec supabase-minio mc mb local/storage --ignore-existing >/dev/null 2>&1
    success "MinIO storage bucket ready"
else
    warn "Could not configure MinIO - storage may not work correctly"
fi

# ---- Step 9: Build and start NoobBook ----
info "Building and starting NoobBook..."
$COMPOSE -f "$ROOT_DIR/docker-compose.yml" --env-file "$NOOBBOOK_ENV" up -d --build

# ---- Step 10: Wait for migration ----
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

# ---- Step 11: Print summary ----
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  NoobBook is running!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  App:              ${CYAN}http://localhost${NC}"
echo -e "  Backend API:      ${CYAN}http://localhost:5001/api/v1${NC}"
echo -e "  Supabase API:     ${CYAN}http://localhost:8000${NC}"
echo -e "  MinIO Console:    ${CYAN}http://localhost:9001${NC}  (supabase/supabase123)"
echo ""
echo -e "  Stop:   ${YELLOW}bash docker/stop.sh${NC}"
echo -e "  Reset:  ${YELLOW}bash docker/reset.sh${NC}"
echo ""
if grep -q '^ANTHROPIC_API_KEY=$' "$NOOBBOOK_ENV" 2>/dev/null; then
    echo -e "${YELLOW}  Remember to add your API keys to docker/.env${NC}"
    echo ""
fi
