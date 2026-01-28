# Supabase Self-Hosting Setup

## Prerequisites

- Docker and Docker Compose
- Git

## 1. Clone Supabase

```bash
git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker
cp .env.example .env
```

## 2. Configure Environment

Edit `.env` file:

```bash
POSTGRES_PASSWORD=your-super-secret-password
JWT_SECRET=your-super-secret-jwt-token-minimum-32-characters
ANON_KEY=your-anon-key
SERVICE_ROLE_KEY=your-service-role-key
```

Generate keys at: https://supabase.com/docs/guides/self-hosting#api-keys

## 3. Start Supabase

```bash
docker compose up -d
```

Default endpoints:
- Studio: http://localhost:3000
- API: http://localhost:8000
- Database: localhost:5432

## 4. Run NoobBook Migrations

Option A - Via Supabase Studio:
1. Open http://localhost:3000
2. Go to SQL Editor
3. Copy contents of `init.sql`
4. Run the query

Option B - Via psql:
```bash
psql -h localhost -p 5432 -U postgres -d postgres -f init.sql
```

## 5. Configure NoobBook

Add to `backend/.env`:

```bash
SUPABASE_URL=http://localhost:8000
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key
```

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

| Bucket | Purpose |
|--------|---------|
| raw-files | Original uploaded files |
| processed-files | Extracted text content |
| chunks | Text chunks for RAG |
| studio-outputs | Generated content |
| brand-assets | Brand logos, fonts |

## Verify Setup

```sql
-- Check tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';

-- Check buckets
SELECT id, name FROM storage.buckets;

-- Check default user
SELECT id, email FROM users;
```

## Troubleshooting

### pgvector extension not available

If using older Supabase version without pgvector:
```sql
-- Skip vector extension, app will work without semantic search
-- Comment out: CREATE EXTENSION IF NOT EXISTS "vector";
```

### Storage policies conflict

If policies already exist:
```sql
-- Drop existing policies first
DROP POLICY IF EXISTS "policy_name" ON storage.objects;
```

### Connection refused

Check Docker containers are running:
```bash
docker compose ps
```
