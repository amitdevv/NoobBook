# Database Sources (MySQL + Postgres)

This PR adds **account-level database connections** (MySQL + PostgreSQL) that can be attached to a project as a **DATABASE source**. Once attached, NoobBook:

- Captures a **schema snapshot** (tables + basic metadata) as the processed content
- Generates embeddings/summaries like other sources (if configured)
- Enables **live, read-only SQL** in chat via `analyze_database_agent`

## Status / Caveat

- **RBAC / “assign users allowed to use the database” is not enforced end-to-end yet.**
  - Tables + backend scaffolding exist (`database_connection_users`), but UI + auth enforcement is deferred to a separate PR.
  - Current flow is **single-user** (`DEFAULT_USER_ID`).

## What Was Added

- Backend
  - Supabase tables: `database_connections`, `database_connection_users` (`backend/supabase/init.sql`)
  - Settings API: `GET/POST/DELETE /api/v1/settings/databases`, `POST /api/v1/settings/databases/validate`
  - Project source attach: `POST /api/v1/projects/<project_id>/sources/database`
  - Processing: `.database` → schema snapshot → processed text (`database_processor.py`)
  - Chat tool: `analyze_database_agent` (read-only SQL, row limit, safe-query validation)
- Frontend
  - App Settings → “Database Connections” CRUD + validate
  - Add Sources → “Database” tab to attach a saved connection to a project
- Local testing
  - Dummy MySQL + Postgres containers: `docker/test-databases/`

## Local Setup (Docker)

1) Environment files:

```bash
cp docker/.env.example docker/.env
cp docker/supabase/.env.example docker/supabase/.env
```

2) Start Supabase:

```bash
docker compose -f docker/supabase/docker-compose.yml up -d
```

3) Start dummy databases (optional but recommended for verification):

```bash
docker compose -f docker/test-databases/docker-compose.yml up -d
```

4) Start NoobBook (runs migrations automatically via `migrate` service):

```bash
docker compose up -d --build
```

Open: `http://localhost`

## Test in the UI (End-to-End)

1) Create connections (account level)
   - Go to **App Settings → Database Connections**
   - Add these (from inside Docker network):
     - Postgres: `postgresql://test_user:test_password@noobbook-test-postgres:5432/test_postgres_db`
     - MySQL: `mysql://test_user:test_password@noobbook-test-mysql:3306/test_mysql_db`
   - Click **Validate** then **Save**

2) Attach to a project
   - Open any Project
   - **Add Sources → Database**
   - Select a connection and click **Add database source**
   - Wait until the source reaches **ready**

3) Query via chat
   - Ask: “In the Test Postgres database source, how many customers exist?”
   - Expected: the assistant uses `analyze_database_agent` and returns `5` (with the seeded dummy DBs)

## Notes for Verification / Troubleshooting

- If “Select connection” already shows entries, they are persisted in Supabase. Delete them from **App Settings → Database Connections**.
- The SQL runner is **read-only**:
  - Only `SELECT`/`WITH` allowed
  - Max rows returned per query: `100`

## Stop Services

```bash
docker compose down
docker compose -f docker/test-databases/docker-compose.yml down
docker compose -f docker/supabase/docker-compose.yml down
```

