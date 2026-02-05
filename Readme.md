# NoobBook

<p align="center">
  <img src="assets/noob_book.png" alt="NoobBook Logo" width="120">
</p>

<p align="center">
  <strong>NotebookLM, but smarter.</strong>
</p>

<p align="center">
  An open-source NotebookLM alternative. Free to use, fork, and self-host.
</p>

<p align="center">
  <a href="https://noobbooklm.com">noobbooklm.com</a>
</p>

---

### First Believer & Primary Sponsor

<p align="center">
  <a href="https://www.delta.exchange">
    <img src="assets/delta_exchange.svg" alt="Delta Exchange" width="300">
  </a>
</p>

<p align="center">
  <em>Thank you Delta Exchange for believing in NoobBook from day one.</em>
</p>

<p align="center">
  <a href="SPONSORS.md">Want to sponsor? See how</a>
</p>

---

### Special Thanks

<p align="center">
  <a href="https://www.growthx.club">
    <img src="assets/growthxlogo.jpeg" alt="GrowthX" width="80">
  </a>
</p>

<p align="center">
  <em>GrowthX - The community that helped shape this journey.</em>
</p>

**Built with:**
[Claude](https://anthropic.com) & [Claude Code](https://claude.ai/code) |
[OpenAI](https://openai.com) |
[ElevenLabs](https://elevenlabs.io) |
[Pinecone](https://pinecone.io) |
[Tavily](https://tavily.com) |
[Google AI](https://ai.google)

**Powered by open-source:**
[React](https://react.dev) |
[Vite](https://vitejs.dev) |
[Flask](https://flask.palletsprojects.com) |
[shadcn/ui](https://ui.shadcn.com) |
[Tailwind CSS](https://tailwindcss.com) |
[Radix UI](https://radix-ui.com)

---

## What is NoobBook?

NoobBook is a fully-featured NotebookLM alternative that you can run yourself. Upload documents, chat with your sources using RAG, and generate content with AI agents.

**Core Features:**
- Multi-modal source ingestion (PDF, DOCX, PPTX, images, audio, YouTube, URLs)
- RAG-powered chat with citations
- AI-generated content (audio overviews, mind maps, presentations, and more)
- Memory system for personalized responses
- Voice input and text-to-speech

---

## How It Works

NoobBook has 4 main concepts:

### 1. Projects

Everything is organized into projects. Each project has its own sources, chats, and studio outputs.

### 2. Sources (Left Panel)

Upload documents and the system processes them for AI understanding:

| Source Type | Processing |
|-------------|------------|
| PDF | AI vision extracts text page by page |
| DOCX | Python extraction |
| PPTX | Convert to PDF, then vision extraction |
| Images | AI vision describes content |
| Audio | ElevenLabs transcription |
| YouTube | Transcript API |
| URLs | Web agent fetches and extracts content |
| Text | Direct input |

**Processing Pipeline:**
```
Upload -> Raw file saved -> AI extracts text -> Chunked for RAG -> Embedded in Pinecone
```

### 3. Chat (Center Panel)

RAG-powered Q&A with your sources:

```
User question
    -> AI searches relevant sources (hybrid: keyword + semantic)
    -> AI generates response with citations
    -> Citations link to specific chunks
```

**Key features:**
- Chunk-based citations
- Memory system (user preferences + project context)
- Voice input via ElevenLabs
- Conversation history per chat

### 4. Studio (Right Panel)

Generate content from your sources using AI agents:

| Category | Studio Items |
|----------|--------------|
| **Audio/Video** | Audio Overview, Video Generation |
| **Learning** | Flash Cards, Mind Maps, Quizzes |
| **Documents** | PRD, Blog Posts, Business Reports, Presentations |
| **Marketing** | Ad Creatives, Social Posts, Email Templates |
| **Design** | Websites, Components, Wireframes, Flow Diagrams |

---

## Architecture

```
Frontend (React + Vite)
    |
    v
Backend API (Flask + SocketIO)
    |
    ├── Source Processing (upload, extract, chunk, embed)
    ├── Chat Service (RAG search, Claude API, citations)
    ├── Studio Services (content generation agents)
    └── Integrations (Claude, OpenAI, Pinecone, ElevenLabs, Gemini)
    |
    v
Supabase (PostgreSQL + S3 Storage + Auth)
```

**AI Services:**
- **Claude** - Main LLM for chat, agents, content generation
- **OpenAI** - Embeddings for vector search
- **Pinecone** - Vector database for RAG
- **ElevenLabs** - Text-to-speech and transcription
- **Gemini** - Image generation
- **Google Veo** - Video generation

---

## Getting Started

### Prerequisites

| Requirement | Install |
|-------------|---------|
| **Python 3.10+** | `brew install python3` (macOS) / `sudo apt install python3 python3-venv` (Ubuntu) |
| **Node.js 18+** | `brew install node` (macOS) / [nodesource](https://github.com/nodesource/distributions) (Ubuntu) |
| **Docker & Docker Compose** | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **LibreOffice** (optional) | `brew install libreoffice` / `sudo apt install libreoffice` — for DOCX/PPTX |
| **FFmpeg** (optional) | `brew install ffmpeg` / `sudo apt install ffmpeg` — for audio |

### API Keys

You'll need these before the app will work:

| Key | Where to get it | Required? |
|-----|-----------------|-----------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Yes |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/) | Yes |
| `PINECONE_API_KEY` + `PINECONE_INDEX_NAME` | [pinecone.io](https://www.pinecone.io/) | Yes |
| `ELEVENLABS_API_KEY` | [elevenlabs.io](https://elevenlabs.io/) | No — audio features |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com/) | No — web search fallback |
| `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` | [Google Cloud Console](https://console.cloud.google.com/) | No — Google Drive import |
| `JIRA_DOMAIN` + `JIRA_EMAIL` + `JIRA_API_KEY` | [Jira Settings → Security → API tokens](https://id.atlassian.com/manage-profile/security/api-tokens) | No — Jira integration |
| `NOTION_API_KEY` | [Notion Integrations](https://www.notion.so/my-integrations) | No — Notion integration |

---

### Auth & Roles (RBAC)

NoobBook supports two roles:
- **admin**: can view/update secrets and app-level settings
- **user**: can chat, use studio, and manage projects

Configure in `docker/.env`:
```
NOOBBOOK_AUTH_REQUIRED=false   # set true to require login for all API routes
NOOBBOOK_ADMIN_EMAILS=you@company.com,admin@company.com
```

First signup becomes admin if no admins exist (or if email is in `NOOBBOOK_ADMIN_EMAILS`).

Optional local bootstrap (creates or resets an admin user on startup):
```
NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD=Admin123!
NOOBBOOK_BOOTSTRAP_ADMIN_FORCE_RESET=true
```

---

### Option A: Docker Setup (Recommended)

One script starts everything — Supabase, database migrations, backend, and frontend.

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
bash docker/setup.sh          # Re-run (idempotent, safe to re-run)
bash docker/reset.sh          # Stop all services
bash docker/reset.sh -v       # Stop + delete ALL data (destructive)
```

| Service | URL |
|---------|-----|
| NoobBook | `http://localhost` |
| Backend API | `http://localhost:5001/api/v1` |
| Supabase Studio | `http://localhost:8000` |

---

### Option B: Local Development

Run backend and frontend locally, but you still need Supabase running (via Docker or Supabase Cloud).

**Step 1: Start Supabase**

```bash
# Self-hosted via Docker
cp docker/supabase/.env.example docker/supabase/.env
# Edit docker/supabase/.env (see backend/supabase/SETUP.md for details)
docker network create noobbook-network
docker compose -f docker/supabase/docker-compose.yml --env-file docker/supabase/.env up -d

# Or use Supabase Cloud — get keys from https://app.supabase.com/project/_/settings/api
```

**Step 2: Run database migrations**

```bash
# Via psql
psql -h localhost -p 5432 -U postgres -d postgres -f backend/supabase/init.sql

# Or via Supabase Studio → SQL Editor → paste contents of init.sql → Run
```

**Step 3: Configure environment**

```bash
cp backend/.env.template backend/.env
nano backend/.env
```

Add your API keys AND Supabase keys:
```bash
# Required API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...

# Required Supabase keys (app won't start without these)
SUPABASE_URL=http://localhost:8000
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
```

**Step 4: Install and run**

macOS / Linux:
```bash
bin/setup                     # First time — creates venv, installs all deps
bin/dev                       # Starts backend (:5001) + frontend (:5173)

# Options
bin/dev --backend-only        # Only Flask server
bin/dev --frontend-only       # Only Vite server
bin/dev --install             # Update deps before starting
```

Windows:
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

cd ../frontend
npm install

python start.py               # Starts both servers
python stop.py                 # Stops both servers
```

**Step 5: Install Playwright (for web scraping)**
```bash
npx playwright install
```

For the full Supabase setup guide, see [`backend/supabase/SETUP.md`](backend/supabase/SETUP.md).

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + Vite + TypeScript |
| UI | shadcn/ui + Tailwind CSS |
| Icons | Phosphor Icons |
| Backend | Python Flask + SocketIO |
| Database | Supabase (PostgreSQL + S3 Storage + Auth) |
| AI/LLM | Claude (Anthropic), OpenAI Embeddings |
| Vector DB | Pinecone |
| Audio | ElevenLabs |
| Image Gen | Google Gemini |
| Video Gen | Google Veo 2.0 |

---

## Contributing

Contributions welcome!

**Branch strategy:**
- `main` - Stable branch for testing and using NoobBook
- `develop` - Latest changes, all PRs go here

**Quick start:**
1. Fork the repo
2. Pull from `develop`
3. Create your branch
4. Open a PR to `develop` (not main)

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details and `CLAUDE.md` for code guidelines.

---

## License 

**License YOLO.v1.01**
- New License type

**Free to use:**
- Fork it, self-host it, use it for yourself or your company

**Want to commercialize it?**
- Become an authorized seller: [noob@noobbooklm.com](mailto:noob@noobbooklm.com)
- Or provide a minimum sponsorship of $10,000 USD

If you commercialize without authorization... well, we're too busy building to chase you. But karma has a way of catching up.

---

**Built with a $10,000 USD sponsorship grant.**
