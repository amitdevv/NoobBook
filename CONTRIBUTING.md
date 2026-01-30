# Contributing to NoobBook

Thanks for your interest in contributing to NoobBook!

## Branch Strategy

We use two main branches:

| Branch | Purpose |
|--------|---------|
| `main` | Stable release (older, JSON-file based storage). Use this to test and play around with NoobBook. |
| `develop` | Latest changes (Supabase, Docker, multi-user). **This is where all new work goes.** |

We don't have a separate staging branch yet — `develop` serves as both development and staging for now.

> **All contributions must target `develop`.** PRs to `main` will be rejected.

---

## Development Setup (develop branch)

The `develop` branch requires **Supabase** (PostgreSQL + Storage + Auth). The app will not start without it.

### Prerequisites

| Requirement | Install |
|-------------|---------|
| **Python 3.10+** | `brew install python3` (macOS) / `sudo apt install python3 python3-venv` (Ubuntu) |
| **Node.js 18+** | `brew install node` (macOS) / [nodesource](https://github.com/nodesource/distributions) (Ubuntu) |
| **Docker & Docker Compose** | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **LibreOffice** (optional) | `brew install libreoffice` / `sudo apt install libreoffice` — for DOCX/PPTX processing |
| **FFmpeg** (optional) | `brew install ffmpeg` / `sudo apt install ffmpeg` — for audio processing |

### API Keys You'll Need

Get these before starting:

| Key | Where to get it | Required? |
|-----|-----------------|-----------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Yes |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/) | Yes |
| `PINECONE_API_KEY` + `PINECONE_INDEX_NAME` | [pinecone.io](https://www.pinecone.io/) | Yes |
| `ELEVENLABS_API_KEY` | [elevenlabs.io](https://elevenlabs.io/) | No — audio features |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com/) | No — web search fallback |
| `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` | [Google Cloud Console](https://console.cloud.google.com/) | No — Google Drive import |

### Option A: Docker Setup (Recommended)

This starts everything — Supabase, backend, frontend, and runs database migrations automatically.

```bash
# 1. Clone and switch to develop
git clone https://github.com/amitdevv/NoobBook.git
cd NoobBook
git checkout develop

# 2. Copy env template and add your API keys
cp docker/.env.example docker/.env
nano docker/.env    # Add ANTHROPIC_API_KEY, OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME

# 3. Run setup (generates Supabase secrets, starts everything)
bash docker/setup.sh

# 4. Open NoobBook
open http://localhost
```

**Manage Docker setup:**
```bash
bash docker/stop.sh           # Stop all services (data preserved)
bash docker/setup.sh          # Re-run setup (idempotent, safe to re-run)
bash docker/reset.sh          # Stop all services
bash docker/reset.sh -v       # Stop + delete ALL data (destructive)
```

| Service | URL |
|---------|-----|
| NoobBook | `http://localhost` |
| Backend API | `http://localhost:5001/api/v1` |
| Supabase Studio | `http://localhost:8000` |

**Supabase Studio login:** The setup script auto-generates the dashboard password. To find it:
```bash
grep DASHBOARD docker/supabase/.env
```
Default username is `supabase`.

### Option B: Local Development (Without Docker for the App)

You still need Supabase running. Either use Docker for just Supabase, or connect to a Supabase Cloud instance.

**Step 1: Start Supabase (pick one)**

```bash
# Option: Self-hosted Supabase via Docker
cp docker/supabase/.env.example docker/supabase/.env
# Edit docker/supabase/.env with generated secrets (see backend/supabase/SETUP.md)
docker network create noobbook-network
docker compose -f docker/supabase/docker-compose.yml --env-file docker/supabase/.env up -d

# Option: Supabase Cloud
# Get keys from https://app.supabase.com/project/_/settings/api
```

**Step 2: Run database migrations**

```bash
# Via psql (self-hosted)
psql -h localhost -p 5432 -U postgres -d postgres -f backend/supabase/init.sql

# Or via Supabase Studio: open http://localhost:8000 → SQL Editor → paste init.sql → Run
```

**Step 3: Configure environment**

```bash
cp backend/.env.template backend/.env
nano backend/.env
```

Fill in your API keys AND the Supabase keys:
```bash
# Required API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...

# Required Supabase keys (app won't start without these)
SUPABASE_URL=http://localhost:8000          # Or your Supabase Cloud URL
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
```

**Step 4: Install and run**

```bash
# macOS / Linux
bin/setup                     # Creates venv, installs all dependencies
bin/dev                       # Starts backend (:5001) + frontend (:5173)

# Windows
cd backend && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
cd ../frontend && npm install
python start.py               # Starts both servers
python stop.py                # Stops both servers
```

**Step 5: Install Playwright (for web scraping)**
```bash
npx playwright install
```

For the full self-hosted Supabase guide, see [`backend/supabase/SETUP.md`](backend/supabase/SETUP.md).

---

## How to Contribute

1. **Fork the repository**

2. **Pull from `develop`** (not main)
   ```bash
   git checkout develop
   git pull origin develop
   ```

3. **Create your feature branch**
   ```bash
   git checkout -b your-feature-name
   ```

4. **Make your changes**
   - See `CLAUDE.md` for code guidelines
   - Follow existing patterns in the codebase

5. **Run tests**
   ```bash
   cd backend && pytest
   ```

6. **Push and create a Pull Request to `develop`**
   ```bash
   git push origin your-feature-name
   ```
   Then open a PR targeting the `develop` branch.

## Important

- PRs to `main` will be rejected — always target `develop`
- Keep PRs focused on a single feature or fix
- See `CLAUDE.md` for code style, design system, and architecture details

## Questions?

Open an issue or reach out at [noob@noobbooklm.com](mailto:noob@noobbooklm.com)
