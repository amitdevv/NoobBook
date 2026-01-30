# macOS Local Setup Guide

This guide covers setting up NoobBook with self-hosted Supabase on macOS.

## Prerequisites

### Required Software
```bash
# Install Docker Desktop for Mac
# Download from: https://www.docker.com/products/docker-desktop/

# Verify Docker is running
docker --version
docker-compose --version
```

### Required API Keys
You'll need the following API keys:
- **Anthropic API Key** (required) - Get from https://console.anthropic.com
- **OpenAI API Key** (required) - Get from https://platform.openai.com
- **Pinecone API Key** (required) - Get from https://www.pinecone.io
- **ElevenLabs API Key** (optional) - For audio features
- **Tavily API Key** (optional) - For web search fallback
- **Google OAuth** (optional) - For Google Drive import

## Quick Start

### 1. Clone and Navigate
```bash
git clone https://github.com/your-repo/NoobBook.git
cd NoobBook/docker
```

### 2. Configure Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=your-index-name

# Optional
ELEVENLABS_API_KEY=...
TAVILY_API_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Anthropic Tier (1-4, controls rate limits)
ANTHROPIC_TIER=1
```

### 3. Run Setup Script
```bash
chmod +x setup.sh
./setup.sh
```

This script will:
- Generate secure passwords and JWT secrets
- Create the Supabase `.env` file
- Initialize the Docker network
- Start all containers
- Run database migrations
- Create MinIO storage bucket

### 4. Verify Installation
```bash
# Check all containers are running
docker ps

# You should see 16 containers:
# - noobbook-frontend
# - noobbook-backend
# - supabase-db
# - supabase-kong
# - supabase-auth
# - supabase-rest
# - supabase-storage
# - supabase-minio
# - supabase-studio
# - supabase-realtime
# - supabase-analytics
# - supabase-edge-functions
# - supabase-imgproxy
# - supabase-pooler
# - supabase-meta
# - supabase-vector
```

### 5. Access the Application
- **Frontend**: http://localhost:80
- **Backend API**: http://localhost:5001/api/v1
- **Supabase API**: http://localhost:8000
- **MinIO Console**: http://localhost:9001 (supabase/supabase123)

## Manual Setup (If setup.sh fails)

### Step 1: Create Docker Network
```bash
docker network create noobbook-network
```

### Step 2: Generate Supabase Secrets
```bash
cd supabase
cp .env.example .env

# Generate secure values (or use these commands)
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 40)
JWT_SECRET=$(openssl rand -base64 64 | tr -dc 'a-zA-Z0-9' | head -c 64)

# Edit supabase/.env and set:
# - POSTGRES_PASSWORD
# - JWT_SECRET
# - ANON_KEY (generate at https://supabase.com/docs/guides/self-hosting#api-keys)
# - SERVICE_ROLE_KEY
```

### Step 3: Start Supabase
```bash
cd supabase
docker-compose up -d
```

### Step 4: Wait for Database Health
```bash
# Wait until supabase-db is healthy
docker ps --filter "name=supabase-db" --format "{{.Status}}"
# Should show: Up X minutes (healthy)
```

### Step 5: Create MinIO Bucket
```bash
# This is required for file storage on macOS
docker exec supabase-minio mc alias set local http://localhost:9000 supabase supabase123
docker exec supabase-minio mc mb local/storage --ignore-existing
```

### Step 6: Start NoobBook
```bash
cd ..  # Back to docker/
docker-compose up -d
```

### Step 7: Run Migrations
```bash
docker-compose run --rm migrate
```

## macOS-Specific Notes

### Storage Backend (MinIO)
macOS Docker doesn't support extended file attributes (xattr) which Supabase Storage requires. This setup uses MinIO as an S3-compatible storage backend instead of the default file system backend.

The storage configuration in `supabase/docker-compose.yml`:
```yaml
storage:
  environment:
    STORAGE_BACKEND: s3
    STORAGE_S3_BUCKET: storage
    STORAGE_S3_ENDPOINT: http://minio:9000
    STORAGE_S3_FORCE_PATH_STYLE: "true"
    AWS_ACCESS_KEY_ID: supabase
    AWS_SECRET_ACCESS_KEY: supabase123
```

### Port Conflicts
If you have other services running, you may need to stop them:
```bash
# Check what's using common ports
lsof -i :80    # Frontend
lsof -i :5001  # Backend
lsof -i :8000  # Supabase Kong
lsof -i :5432  # PostgreSQL

# Stop conflicting containers
docker stop <container-name>
```

### Docker Resources
For best performance, allocate in Docker Desktop:
- **Memory**: 8GB minimum (12GB recommended)
- **CPUs**: 4 minimum
- **Disk**: 20GB minimum

Settings: Docker Desktop > Preferences > Resources

## Troubleshooting

### Container Won't Start
```bash
# Check container logs
docker logs <container-name>

# Restart specific container
docker-compose restart <service-name>

# Rebuild and restart
docker-compose up -d --build <service-name>
```

### Database Connection Issues
```bash
# Check if database is healthy
docker exec supabase-db pg_isready -U postgres

# Check database logs
docker logs supabase-db

# Connect to database directly
docker exec -it supabase-db psql -U postgres
```

### Storage Upload Failures
```bash
# Verify MinIO is running
docker logs supabase-minio

# Check if bucket exists
docker exec supabase-minio mc ls local/

# Recreate bucket if needed
docker exec supabase-minio mc mb local/storage --ignore-existing

# Check storage container logs
docker logs supabase-storage
```

### Edge Functions Errors
The edge functions container may show warnings - this is normal if you're not using Supabase Edge Functions. A placeholder function is provided to prevent crashes.

### Reset Everything
```bash
# Stop all containers
docker-compose -f docker-compose.yml -f supabase/docker-compose.yml down

# Remove volumes (WARNING: deletes all data)
docker-compose -f docker-compose.yml -f supabase/docker-compose.yml down -v

# Remove network
docker network rm noobbook-network

# Start fresh
./setup.sh
```

## Service URLs Reference

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:80 | NoobBook web application |
| Backend API | http://localhost:5001/api/v1 | REST API |
| Supabase Kong | http://localhost:8000 | API Gateway |
| Supabase Studio | http://localhost:8000 | Database dashboard (via Kong) |
| MinIO Console | http://localhost:9001 | Storage browser |
| PostgreSQL | localhost:5432 | Database (direct) |
| Pooler | localhost:6543 | Connection pooler |

## Stopping the Application

```bash
# Stop all containers (preserves data)
cd docker
docker-compose -f docker-compose.yml -f supabase/docker-compose.yml down

# Stop and remove volumes (deletes data)
docker-compose -f docker-compose.yml -f supabase/docker-compose.yml down -v
```

## Updating

```bash
# Pull latest changes
git pull

# Rebuild containers
cd docker
docker-compose -f docker-compose.yml -f supabase/docker-compose.yml up -d --build

# Run any new migrations
docker-compose run --rm migrate
```
