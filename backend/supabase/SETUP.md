# Supabase Self-Hosting Setup

Run NoobBook with a self-hosted Supabase instance using Docker.

> **Note:** Supabase is required — the app will not start without it. There is no JSON file fallback.

## Quick Start (Docker)

### Prerequisites

- Docker and Docker Compose
- Git
- Minimum: 4 GB RAM, 2 CPU cores, 50 GB SSD (8 GB RAM recommended)

### 3 Commands

```bash
# 1. Copy the env template and add your API keys
cp docker/.env.example docker/.env
nano docker/.env

# 2. Run the setup script (generates secrets, starts everything)
bash docker/setup.sh

# 3. Open NoobBook
open http://localhost
```

That's it. The setup script handles:
- Generating all Supabase secrets (JWT, passwords, tokens)
- Creating the Docker network
- Starting Supabase (13 services)
- Waiting for the API gateway to become healthy
- Running database migrations (`init.sql`)
- Building and starting NoobBook (backend + frontend)

### What You Need in `docker/.env`

Only the API keys — everything else is auto-generated:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...

# Optional
ELEVENLABS_API_KEY=...          # Audio features
TAVILY_API_KEY=...              # Web search fallback
GOOGLE_CLIENT_ID=...            # Google Drive import
GOOGLE_CLIENT_SECRET=...
```

### Managing the Setup

```bash
bash docker/stop.sh             # Stop all services (data preserved)
docker compose up -d             # Restart NoobBook only
bash docker/setup.sh            # Re-run setup (idempotent, skips existing .env)
bash docker/reset.sh            # Stop all services
bash docker/reset.sh -v         # Stop + delete ALL data (destructive)
```

### Default Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| NoobBook | `http://localhost` | Main application |
| Backend API | `http://localhost:5001/api/v1` | Flask API (also proxied via nginx) |
| Supabase API Gateway | `http://localhost:8000` | Kong gateway (internal) |

### Architecture

```
Browser → nginx:80
  ├── /            → static React build
  ├── /api/*       → proxy to backend:5001
  └── /socket.io/* → proxy to backend:5001 (WebSocket)

backend:5001 → supabase-kong:8000 (Supabase API gateway)
```

All containers share the `noobbook-network` Docker network. The single nginx port eliminates CORS issues.

### Data Persistence

| Data | Location | Survives restart? |
|------|----------|-------------------|
| PostgreSQL | Supabase Docker volume | Yes |
| Uploaded files | Supabase storage volume | Yes |
| Prompt configs | `noobbook-backend-data` volume | Yes |
| Generated secrets | `docker/.env`, `docker/supabase/.env` | Yes (on host) |

Only `bash docker/reset.sh -v` destroys data.

---

## Manual Setup (Without the Script)

If you prefer to set up each piece yourself, or need to connect to an existing Supabase instance.

### 1. Set Up Supabase

Clone the official repo and copy the Docker setup:

```bash
git clone --depth 1 https://github.com/supabase/supabase
mkdir supabase-project
cp -rf supabase/docker/* supabase-project
cp supabase/docker/.env.example supabase-project/.env
cd supabase-project
```

### 2. Configure Environment

Edit the `.env` file in your `supabase-project` directory.

#### Database & Auth Keys

```bash
POSTGRES_PASSWORD=your-super-secret-password          # Letters + numbers only (avoid special chars)
JWT_SECRET=your-super-secret-jwt-token-min-32-chars   # Min 32 characters
ANON_KEY=your-generated-anon-key                      # JWT with anon role
SERVICE_ROLE_KEY=your-generated-service-role-key       # JWT with service_role (never expose client-side)
```

Generate `ANON_KEY` and `SERVICE_ROLE_KEY` at: https://supabase.com/docs/guides/self-hosting#api-keys

#### Service Secrets

Required for Supabase internal services:

```bash
SECRET_KEY_BASE=your-64-char-secret                   # Realtime & Supavisor
VAULT_ENC_KEY=your-32-char-hex                        # Supavisor config encryption (exactly 32 chars)
PG_META_CRYPTO_KEY=your-32-char-secret                # Connection string encryption
LOGFLARE_PUBLIC_ACCESS_TOKEN=your-32-char-token       # Log ingestion
LOGFLARE_PRIVATE_ACCESS_TOKEN=your-32-char-token      # Logflare admin
```

Generate them:
```bash
openssl rand -base64 48     # SECRET_KEY_BASE (64+ chars)
openssl rand -hex 16        # VAULT_ENC_KEY (exactly 32 chars)
openssl rand -base64 24     # PG_META_CRYPTO_KEY
openssl rand -base64 24     # LOGFLARE_PUBLIC_ACCESS_TOKEN
openssl rand -base64 24     # LOGFLARE_PRIVATE_ACCESS_TOKEN
```

#### Dashboard Access

```bash
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=your-dashboard-password
```

#### Remote Access (skip if localhost only)

```bash
SUPABASE_PUBLIC_URL=http://your-server-ip:8000
API_EXTERNAL_URL=http://your-server-ip:8000
SITE_URL=http://your-server-ip:5173
```

### 3. Start Supabase

```bash
docker compose pull
docker compose up -d
docker compose ps    # Verify all services show Up (healthy)
```

### 4. Run NoobBook Migrations

**Option A — Via Supabase Studio (recommended):**
1. Open `http://localhost:8000`
2. Go to SQL Editor
3. Paste the contents of `init.sql`
4. Run the query

**Option B — Via psql:**
```bash
psql -h localhost -p 5432 -U postgres -d postgres -f init.sql
```

This creates all tables, indexes, triggers, storage buckets, and the default single-user account.

#### About pgvector

`init.sql` includes `CREATE EXTENSION IF NOT EXISTS "vector"`. If your Supabase version doesn't support pgvector, comment out that line — the app works without it (semantic search falls back to keyword search).

### 5. Configure NoobBook Backend

Add these to `backend/.env`:

```bash
SUPABASE_URL=http://localhost:8000
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key
```

If running on a remote server, replace `localhost` with your server IP/domain.

> **Single-user mode:** The backend uses `SUPABASE_SERVICE_KEY` which bypasses Row Level Security. This is correct for single-user deployments.

### 6. Start NoobBook

```bash
bin/dev
```

The backend should print `✓ Supabase client initialized (service key): http://localhost:8000` on startup.

---

## Google Drive (Optional)

OAuth callback URLs are currently hardcoded to `localhost:5001` (backend) and `localhost:5173` (frontend). Register in Google Cloud Console:

```
Redirect URI: http://localhost:5001/api/v1/google/callback
```

For remote servers, update the URLs in the code to match your server address.

## Deploying with Coolify

Coolify doesn't have a one-click Supabase template. Deploy as a custom Docker Compose service:

1. Create a new service in Coolify and choose "Docker Compose"
2. Point it to the Supabase `docker-compose.yml`
3. Add all environment variables in Coolify's service settings
4. Deploy NoobBook as a separate service, with `SUPABASE_URL` pointing to the Supabase service's internal URL

## File Structure

```
supabase/
  init.sql              # Complete schema (run for fresh setup)
  migrations/           # Individual migrations (for incremental updates)
    00001_initial_schema.sql
    00002_storage_buckets.sql
    00003_rls_policies.sql
    00004_functions_triggers.sql
    00005_enable_pgvector.sql
    00006_user_roles.sql
    00007_brand_assets.sql
    00008_google_oauth_tokens.sql
```

- **Fresh setup:** Run `init.sql` (combines all migrations)
- **Incremental update:** Run only the new migration file

## Database Schema

| Table | Purpose |
|-------|---------|
| users | User accounts, memory, settings, google_tokens |
| projects | Project metadata, prompts, costs |
| sources | Source files metadata |
| chats | Chat containers |
| messages | Chat messages |
| chunks | RAG text chunks |
| background_tasks | Async task tracking |
| studio_signals | Studio feature signals |
| brand_assets | Brand asset metadata |
| brand_config | Brand configuration |

## Storage Buckets

| Bucket | Size Limit | Purpose |
|--------|-----------|---------|
| raw-files | 100 MB | Original uploaded files |
| processed-files | 100 MB | Extracted text content |
| chunks | 10 MB | Text chunks for RAG |
| studio-outputs | 500 MB | Generated content |
| brand-assets | 50 MB | Brand logos, fonts |

All buckets are auto-created by `init.sql` with `ON CONFLICT DO NOTHING` (safe to re-run).

## Troubleshooting

### Services not starting / unhealthy

```bash
docker compose ps                    # Check status
docker compose logs <service-name>   # Check specific service logs
docker compose logs analytics        # Logflare often fails first if tokens missing
```

Most startup failures are due to missing secrets. All five service secrets are required.

### pgvector extension not available

```sql
-- Comment out this line in init.sql, app works without semantic search
-- CREATE EXTENSION IF NOT EXISTS "vector";
```

### Storage policies conflict

```sql
DROP POLICY IF EXISTS "Allow all on raw-files" ON storage.objects;
DROP POLICY IF EXISTS "Allow all on processed-files" ON storage.objects;
DROP POLICY IF EXISTS "Allow all on chunks" ON storage.objects;
DROP POLICY IF EXISTS "Allow all on studio-outputs" ON storage.objects;
DROP POLICY IF EXISTS "Allow all on brand-assets" ON storage.objects;
```

### Connection refused

```bash
docker compose ps                                    # Are containers running?
docker compose down && docker compose up -d          # Restart everything
```

### Backend says "Supabase is not configured"

Check `backend/.env` (manual setup) or `docker/.env` (Docker setup) has:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_ANON_KEY`

## Stopping / Removing

```bash
# Docker setup
bash docker/stop.sh              # Stop all services (data preserved)
bash docker/reset.sh -v          # Stop + delete ALL data

# Manual setup
docker compose down              # Stop services (data preserved)
docker compose down -v           # Stop + delete volumes (destroys data)
rm -rf volumes/db/data           # Delete PostgreSQL data
rm -rf volumes/storage           # Delete stored files
```
