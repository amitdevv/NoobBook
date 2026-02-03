# NoobBook Codebase Overview

This document is a practical map of the repo: what lives where, the main runtime flows, and which files to read first when you’re debugging or extending the app.

## What this app is

NoobBook is a NotebookLM-style app:

- **Frontend**: React + Vite + TypeScript + Tailwind + shadcn/ui
- **Backend**: Flask + Flask-SocketIO
- **Persistence**: **Supabase** (Postgres tables + Storage buckets)
- **RAG**: OpenAI embeddings → Pinecone vector search → chunk retrieval from Supabase Storage
- **Agents / Tools**: Claude tool-use loops for chat + studio generators

## Repo layout (top-level)

- `backend/` — Flask API, background jobs, AI/tool integrations
- `frontend/` — React UI (Dashboard + Project workspace)
- `docker/` + `docker-compose.yml` — full-stack self-host setup (Supabase + app)
- `bin/` — local dev scripts (`bin/setup`, `bin/dev`)
- `start.py` / `stop.py` — cross-platform helper scripts

## How to run (dev)

- Local dev: `bin/setup` then `bin/dev`
- Docker: `bash docker/setup.sh` (see `Readme.md`)

## Backend: mental model

### Entry points

- `backend/run.py` — starts the Flask app (and clears `__pycache__` in repo code)
- `backend/app/__init__.py` — Flask application factory (`create_app`) + SocketIO setup
- `backend/app/api/__init__.py` — registers API blueprints under `/api/v1`

### API surface (where routes live)

Blueprint folders under `backend/app/api/`:

- `projects/` — project CRUD, memory, costs
- `sources/` — upload/manage sources
- `chats/` + `messages/` — chat CRUD + “send message” (main AI entry)
- `studio/` — content generation jobs (audio, blog, presentations, etc.)
- `settings/` — API keys, processing tier config (mostly `.env`-driven)
- `brand/` — brand kit assets + config
- `google/` — OAuth + Drive import
- `prompts/` — read/update prompts

### Persistence model (Supabase)

Schema is defined in `backend/supabase/init.sql`.

Main tables used by the app:

- `users` — single-user default row exists
- `projects` — project metadata + `custom_prompt`, `memory`, `costs`
- `sources` — source metadata + status + `embedding_info`/`summary_info`
- `chats`, `messages` — chat containers + message history (message `content` is JSONB)
- `background_tasks` — tracks ThreadPoolExecutor jobs
- `studio_signals` — chat-scoped “activate studio feature” hints
- `brand_assets`, `brand_config` — brand kit storage

Supabase Storage buckets are used heavily (see `backend/app/services/integrations/supabase/storage_service.py`):

- `raw-files` — original uploads
- `processed-files` — extracted text
- `chunks` — per-chunk text (for citations + retrieval)
- `studio-outputs` — generated artifacts
- `brand-assets` — uploaded brand assets

### Background jobs

No Redis/Celery. Background work is a `ThreadPoolExecutor` + task records in Supabase:

- `backend/app/services/background_services/task_service.py`

Patterns:

- Source processing is queued on upload (non-blocking).
- Studio generation creates a job row then runs generation in background.

## Core flow 1: Sources (upload → process → embed → ready)

Files to read:

- Upload entry: `backend/app/api/sources/routes.py`
- Upload logic: `backend/app/services/source_services/source_upload/file_upload.py`
- Processing dispatcher: `backend/app/services/source_services/source_processing/source_processing_service.py`
- Per-type processors: `backend/app/services/source_services/source_processing/*_processor.py`
- PDF extraction pipeline: `backend/app/services/ai_services/pdf_service.py`
- Embedding pipeline: `backend/app/services/ai_services/embedding_service.py`
- Summary pipeline: `backend/app/services/ai_services/summary_service.py`

High-level state machine (stored in `sources.status`):

1. `uploaded`
2. `processing`
3. `embedding` (optional)
4. `ready` or `error`

Key design points:

- Raw/processed/chunk content is stored in **Supabase Storage**.
- Vectors are stored in **Pinecone**, namespaced by `project_id`.
- Chunk files are the source of truth for citations and retrieval context.

## Core flow 2: Chat (messages + tool loop + citations)

Files to read:

- HTTP entry: `backend/app/api/messages/routes.py`
- Orchestrator: `backend/app/services/chat_services/main_chat_service.py`
- Message CRUD + API message building: `backend/app/services/data_services/message_service.py`
- System prompt config: `backend/app/config/prompt_loader.py`
- Dynamic context (memory + active sources list): `backend/app/config/context_loader.py`
- Claude wrapper: `backend/app/services/integrations/claude/claude_service.py`
- Tool parsing utilities: `backend/app/utils/claude_parsing_utils.py`

Runtime flow (simplified):

1. User POSTs message → backend stores it in `messages`.
2. Backend builds system prompt (default + project custom prompt + memory context + source context).
3. Backend calls Claude with tool definitions.
4. If Claude returns tool calls, backend executes them and posts tool results back into the chat history.
5. Loop continues until Claude returns final text.
6. Assistant message is stored and returned to the UI.

RAG retrieval tool:

- Tool executor: `backend/app/services/tool_executors/source_search_executor.py`
- Strategy:
  - Small sources: return full chunk set
  - Large sources: hybrid search (keyword scan of chunk text + Pinecone semantic search)
  - Output includes `chunk_id` so the model can cite `[[cite:chunk_id]]`

## Core flow 3: Studio (jobs + generated outputs)

Studio is “agentic generation” driven by explicit endpoints (and optionally by chat signals).

Files to read:

- Studio routes: `backend/app/api/studio/*`
- Job tracking: `backend/app/services/studio_services/studio_index_service.py`
- Example generator (audio overview): `backend/app/services/studio_services/audio_overview_service.py`
- Example executor tools (audio): `backend/app/services/tool_executors/studio_audio_executor.py`

Pattern:

1. Create job row (status `pending`)
2. Submit background task
3. Generator writes outputs to Supabase Storage
4. Job updated to `ready` with URLs for the frontend to fetch/stream

## Tools & agents

Tool definitions are JSON files under:

- `backend/app/services/tools/`
  - `chat_tools/` (chat-time tools like source search, memory, KB integrations)
  - `studio_tools/` (generator tool loops)
  - plus agent-specific tool categories

Tool execution code lives under:

- `backend/app/services/tool_executors/`

## Frontend: mental model

### Entry points + routing

- `frontend/src/main.tsx` → mounts `<App />`
- `frontend/src/App.tsx` → React Router
  - `/` → Dashboard
  - `/projects/:projectId` → Workspace (Sources + Chat + Studio panels)
  - `/projects/:projectId/brand` → Brand Kit page

### API client

- `frontend/src/lib/api/client.ts`
  - `API_HOST` defaults to `http://localhost:5001`
  - `API_BASE_URL` defaults to `${API_HOST}/api/v1`
  - Docker/nginx can set `VITE_API_HOST=""` for same-origin proxying

### Workspace composition

- `frontend/src/components/project/ProjectWorkspace.tsx`
  - Left: Sources (`SourcesPanel`)
  - Center: Chat (`ChatPanel`)
  - Right: Studio (`StudioPanel`)

## Notes / gotchas

- The repo contains some legacy “file-based storage” utilities (`backend/app/utils/path_utils.py`) that mainly serve backward compatibility and local debug logs; the `develop` branch’s live data path is Supabase (tables + Storage).
- If you run Python compilation checks in a restricted sandbox, you may need to set `PYTHONPYCACHEPREFIX` (example: `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall backend/app -q`).

