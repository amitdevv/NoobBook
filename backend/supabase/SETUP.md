# Supabase Self-Hosting Setup

Guide to run NoobBook with a self-hosted Supabase instance on your own server (bare metal, VPS, or Docker host).

> **Note:** Supabase is required — the app will not start without it. There is no JSON file fallback.

## Prerequisites

- Docker and Docker Compose
- Git
- Minimum: 4 GB RAM, 2 CPU cores, 50 GB SSD (8 GB RAM recommended)

## 1. Set Up Supabase

Clone the official repo and copy the Docker setup to a separate directory (keeps your config safe from repo updates):

```bash
git clone --depth 1 https://github.com/supabase/supabase
mkdir supabase-project
cp -rf supabase/docker/* supabase-project
cp supabase/docker/.env.example supabase-project/.env
cd supabase-project
```

## 2. Configure Environment

Edit the `.env` file in your `supabase-project` directory.

### Required: Database & Auth Keys

```bash
POSTGRES_PASSWORD=your-super-secret-password          # Letters + numbers only (avoid special chars)
JWT_SECRET=your-super-secret-jwt-token-min-32-chars   # Min 32 characters
ANON_KEY=your-generated-anon-key                      # JWT with anon role
SERVICE_ROLE_KEY=your-generated-service-role-key       # JWT with service_role (never expose client-side)
```

Generate `ANON_KEY` and `SERVICE_ROLE_KEY` at: https://supabase.com/docs/guides/self-hosting#api-keys

Or use the built-in script:
```bash
sh ./utils/generate-keys.sh
```

### Required: Service Secrets

These are needed for Supabase internal services to start healthy:

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

### Required: Dashboard Access

Protects Supabase Studio UI with basic auth:

```bash
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=your-dashboard-password            # Alphanumeric, min one letter
```

### Required for Remote Access (skip if localhost only)

If running on a remote server (not localhost), set these so auth redirects and API calls work:

```bash
SUPABASE_PUBLIC_URL=http://your-server-ip:8000
API_EXTERNAL_URL=http://your-server-ip:8000
SITE_URL=http://your-server-ip:5173
```

## 3. Start Supabase

```bash
docker compose pull
docker compose up -d
```

Verify all services are healthy:
```bash
docker compose ps
```

All services should show `Up (healthy)` within a minute.

### Default Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| API Gateway (Kong) | `http://localhost:8000` | REST API + Studio dashboard |
| PostgreSQL | `localhost:5432` | Direct database access |

> Studio dashboard is accessed through the API gateway at port 8000. Log in with the `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` you set above.

## 4. Run NoobBook Migrations

**Option A — Via Supabase Studio (recommended):**
1. Open `http://localhost:8000` (or your server IP)
2. Go to SQL Editor
3. Paste the contents of `init.sql`
4. Run the query

**Option B — Via psql:**
```bash
psql -h localhost -p 5432 -U postgres -d postgres -f init.sql
```

This creates all tables, indexes, triggers, storage buckets, and the default single-user account.

### About pgvector

`init.sql` includes `CREATE EXTENSION IF NOT EXISTS "vector"`. If your Supabase version doesn't support pgvector, comment out that line — the app works without it (semantic search falls back to keyword search).

## 5. Configure NoobBook Backend

Add these to `backend/.env`:

```bash
# Supabase (required)
SUPABASE_URL=http://localhost:8000
SUPABASE_SERVICE_KEY=your-service-role-key      # Same key from step 2
SUPABASE_ANON_KEY=your-anon-key                 # Same key from step 2
```

If running on a remote server, replace `localhost` with your server IP/domain.

> **Single-user mode:** The backend uses `SUPABASE_SERVICE_KEY` which bypasses Row Level Security. This is correct for single-user deployments. Multi-user support requires auth middleware (not yet implemented).

## 6. Verify Setup

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';

-- Check storage buckets created
SELECT id, name FROM storage.buckets;

-- Check default user exists
SELECT id, email FROM users;
-- Expected: 00000000-0000-0000-0000-000000000001 | local@noobbook.local
```

Then start NoobBook:
```bash
bin/dev
```

The backend should print `✓ Supabase client initialized (service key): http://localhost:8000` on startup.

## 7. Google Drive (Optional)

If you want Google Drive import, note that OAuth callback URLs are currently hardcoded to `localhost:5001` (backend) and `localhost:5173` (frontend). Register this in Google Cloud Console:

```
Redirect URI: http://localhost:5001/api/v1/google/callback
```

For remote servers, these URLs in the code would need to be updated to match your server address.

## Deploying with Coolify

Coolify doesn't have a one-click Supabase template. Deploy as a custom Docker Compose service:

1. Create a new service in Coolify and choose "Docker Compose"
2. Point it to the Supabase `docker-compose.yml` from step 1
3. Add all environment variables from step 2 in Coolify's service settings
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

Most startup failures are due to missing secrets from step 2. All five service secrets are required.

### pgvector extension not available

```sql
-- Comment out this line in init.sql, app works without semantic search
-- CREATE EXTENSION IF NOT EXISTS "vector";
```

### Storage policies conflict

```sql
-- Drop existing policies first, then re-run init.sql
DROP POLICY IF EXISTS "Allow all on raw-files" ON storage.objects;
DROP POLICY IF EXISTS "Allow all on processed-files" ON storage.objects;
DROP POLICY IF EXISTS "Allow all on chunks" ON storage.objects;
DROP POLICY IF EXISTS "Allow all on studio-outputs" ON storage.objects;
DROP POLICY IF EXISTS "Allow all on brand-assets" ON storage.objects;
```

### Connection refused

```bash
docker compose ps                    # Are containers running?
docker compose down && docker compose up -d   # Restart everything
```

### Backend says "Supabase is not configured"

Check `backend/.env` has all three variables set:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_ANON_KEY`

At minimum, `SUPABASE_URL` and one of the keys must be present.

## Stopping / Removing

```bash
docker compose down          # Stop services (data preserved)
docker compose down -v       # Stop + delete volumes (destroys data)
rm -rf volumes/db/data       # Delete PostgreSQL data
rm -rf volumes/storage       # Delete stored files
```
