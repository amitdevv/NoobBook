# NoobBook — System Design

> **NoobBook** is an open-source NotebookLM alternative. A full-stack web application that combines multi-modal document ingestion, RAG-based conversational AI, and AI-powered content generation.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Frontend Architecture](#2-frontend-architecture)
3. [Backend Architecture](#3-backend-architecture)
4. [RAG Pipeline](#4-rag-pipeline)
5. [Chat Agentic Loop](#5-chat-agentic-loop)
6. [Source Processing Pipeline](#6-source-processing-pipeline)
7. [Studio Content Generation](#7-studio-content-generation)
8. [Data Layer](#8-data-layer)
9. [External Integrations](#9-external-integrations)
10. [Infrastructure & Deployment](#10-infrastructure--deployment)
11. [Key Design Patterns](#11-key-design-patterns)

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND — React + Vite + TypeScript                                   │
│  ┌──────────────┐ ┌──────────────────────┐ ┌─────────────┐ ┌────────┐ │
│  │ React + Vite │ │ Sources|Chat|Studio  │ │ Voice (WS)  │ │Auth JWT│ │
│  └──────────────┘ └──────────────────────┘ └─────────────┘ └────────┘ │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTP / REST
┌────────────────────────────────▼────────────────────────────────────────┐
│  API LAYER — Flask                                                      │
│  ┌──────────────────┐ ┌──────────────┐ ┌───────────────────────┐       │
│  │ Flask /api/v1    │ │ 11 Blueprints│ │ JWT + Auth Middleware │       │
│  └──────────────────┘ └──────────────┘ └───────────────────────┘       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  SERVICE LAYER                                                          │
│  ┌──────────────────┐ ┌────────────────┐ ┌───────────┐ ┌────────────┐ │
│  │ Chat Service     │ │ Source         │ │ AI        │ │ Studio     │ │
│  │ (RAG + Agentic)  │ │ Processing    │ │ Services  │ │ (18 Gen)   │ │
│  └──────────────────┘ └────────────────┘ └───────────┘ └────────────┘ │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  EXTERNAL APIs                                                          │
│  ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ ┌───────┐ │
│  │ Claude │ │ OpenAI │ │Pinecone │ │ElevenLabs│ │ Google │ │Tavily │ │
│  │LLM+Vis│ │Embed   │ │VectorDB │ │Audio+TTS │ │Drive   │ │Search │ │
│  └────────┘ └────────┘ └─────────┘ └──────────┘ └────────┘ └───────┘ │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  DATA LAYER                                                             │
│  ┌───────────────┐ ┌───────────────┐ ┌────────────┐ ┌───────────────┐ │
│  │ PostgreSQL    │ │ S3 Storage    │ │ Pinecone   │ │ Config/Prompts│ │
│  │ 8 Tables+RLS │ │ 5 Buckets     │ │ 1536-dim   │ │ 31 JSON + 70  │ │
│  └───────────────┘ └───────────────┘ └────────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Count

| Layer | Components | Details |
|-------|-----------|---------|
| Frontend | ~270 TSX files | React components, hooks, API clients |
| API Routes | 11 blueprints | ~60+ REST endpoints |
| Services | 50+ service files | Chat, source, AI, studio, background |
| Integrations | 8 external APIs | Claude, OpenAI, Pinecone, ElevenLabs, Google, Tavily, Jira, Notion |
| Data | 8 DB tables | Users, projects, sources, chats, messages, chunks, tasks, brand |
| Config | 31 prompts + 70+ tools | JSON-based prompt and tool definitions |

---

## 2. Frontend Architecture

### Tech Stack

- **Framework**: React 19 + TypeScript + Vite 7
- **UI Library**: shadcn/ui (50+ components built on Radix UI)
- **Styling**: Tailwind CSS + class-variance-authority
- **Icons**: Phosphor Icons (`@phosphor-icons/react`)
- **State**: React Context + Local State (no Redux/Zustand)
- **HTTP Client**: Axios with JWT auto-refresh interceptors
- **Routing**: React Router v6

### Two Core Views

**Dashboard** (`/`)
- Project list with create/open/delete operations
- App-level settings (API keys, integrations, team management)

**Project Workspace** (`/projects/:projectId`)
- 3-panel resizable layout using `react-resizable-panels`:

```
┌────────────────────┬───────────────────────────┬────────────────────────┐
│  SOURCES (20%)     │  CHAT (55%)               │  STUDIO (25%)          │
│                    │                           │                        │
│  Multi-type upload │  RAG Q&A with citations   │  18 content generators │
│  PDF, DOCX, Audio  │  Voice input (ElevenLabs) │  Audio, Video, Docs    │
│  Images, URLs, CSV │  Conversation history     │  Presentations, PRDs   │
│  YouTube, Drive    │  Markdown rendering       │  Mind maps, Quizzes    │
│                    │  Citation tooltips        │  Blogs, Emails, etc.   │
└────────────────────┴───────────────────────────┴────────────────────────┘
```

### State Management

- **No global store** — each panel owns its state via React hooks
- **Cross-panel coordination**: ProjectWorkspace acts as parent orchestrator
- **Per-chat source selection**: Each chat remembers which sources are active
- **Studio signals**: Chat responses trigger studio generation options

### API Layer (`lib/api/`)

- `client.ts` — Axios instance with:
  - Bearer token injection from localStorage
  - Auto-refresh on 401 (shared promise deduplication)
  - Configurable base URL for Docker/local dev
- 25+ API service files organized by feature
- 18 studio-specific API files (one per generator type)

### Authentication Flow

```
App.tsx mounts → authAPI.me() → auth_required?
  ├─ Yes + not authenticated → AuthPage (sign in/up)
  └─ No or authenticated → Dashboard
```

- Tokens stored in localStorage (`noobbook.access_token`, `noobbook.refresh_token`)
- 401 responses trigger transparent token refresh + request retry

---

## 3. Backend Architecture

### Tech Stack

- **Framework**: Flask + Flask-CORS + Flask-SocketIO
- **Python**: 3.11 with type hints (PEP 8)
- **Task Queue**: ThreadPoolExecutor (I/O-bound, no Celery needed)
- **Database**: Supabase (PostgreSQL + PostgREST + S3 Storage)

### Directory Structure

```
backend/app/
├── __init__.py              # Flask app factory + SocketIO
├── api/                     # Route blueprints (11 total)
│   ├── auth/                #   signup, login, logout, refresh
│   ├── projects/            #   CRUD + costs + memory
│   ├── chats/               #   CRUD chat containers
│   ├── messages/            #   Send message (RAG entry point)
│   ├── sources/             #   Upload, process, search
│   ├── studio/              #   18 content generation endpoints
│   ├── settings/            #   API keys, databases, tiers
│   ├── google/              #   OAuth + Drive import
│   ├── transcription/       #   ElevenLabs config
│   ├── brand/               #   Brand assets + config
│   └── prompts/             #   System prompt management
├── config/                  # Configuration loaders
│   ├── prompt_loader.py     #   Load prompts from JSON
│   ├── tool_loader.py       #   Load tool definitions from JSON
│   ├── context_loader.py    #   Build dynamic system prompt context
│   ├── tier_loader.py       #   Rate limits by tier (1-4)
│   └── brand_context_loader.py
├── services/                # Business logic
│   ├── chat_services/       #   main_chat_service.py (RAG core)
│   ├── source_services/     #   Source upload + processing pipeline
│   ├── ai_services/         #   PDF, PPTX, Image, Embedding, Summary
│   ├── ai_agents/           #   Web agent, Blog, Email, PRD, etc.
│   ├── studio_services/     #   18 content generation services
│   ├── tool_executors/      #   Execute Claude tool calls
│   ├── data_services/       #   CRUD for DB entities
│   ├── background_services/ #   ThreadPoolExecutor task queue
│   ├── integrations/        #   External API wrappers
│   └── auth/                #   RBAC + permissions
└── utils/                   # Cross-cutting utilities
    ├── claude_parsing_utils.py  # Centralized Claude response parser
    ├── path_utils.py            # Safe path management
    ├── embedding_utils.py       # Token counting (tiktoken)
    ├── rate_limit_utils.py      # Rate limiter class
    ├── batching_utils.py        # Batch processing helpers
    └── text/                    # RAG text processing
        ├── chunking.py          #   Token-based chunking (~200 tokens)
        ├── cleaning.py          #   Text normalization
        ├── page_markers.py      #   Page marker parsing
        └── processed_output.py  #   Standardized output format
```

### API Endpoints (Key Routes)

| Blueprint | Key Endpoints | Purpose |
|-----------|--------------|---------|
| `auth` | `POST /auth/signup, login, refresh` | User authentication |
| `projects` | `GET/POST/PUT/DELETE /projects` | Project CRUD |
| `chats` | `GET/POST/PUT/DELETE /projects/:id/chats` | Chat management |
| `messages` | `POST /projects/:id/chats/:id/messages` | **RAG chat (core)** |
| `sources` | `POST /projects/:id/sources` (multipart) | Source upload + processing |
| `studio` | `POST /studio/blogs, presentations, ...` | Content generation (18 types) |
| `settings` | `GET/POST /settings/api-keys` | API key management |
| `google` | `GET /google/auth, callback, files` | Google Drive OAuth |

---

## 4. RAG Pipeline

The Retrieval-Augmented Generation pipeline is the core of NoobBook. It transforms uploaded documents into searchable knowledge that Claude can reference with precise citations.

### End-to-End Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. SOURCE INGESTION                                         │
│                                                              │
│  File Upload → Validation → Supabase Storage → Status:       │
│  (PDF, DOCX, PPTX, Image, Audio, URL, YouTube, CSV, Text)   │
│                                                 uploaded     │
└─────────────────────────────┬───────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. TEXT EXTRACTION                          Status:         │
│                                              processing      │
│  Type-specific processors:                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PDF/PPTX  → Claude Vision (batched, 5 pages/batch)    │ │
│  │ Image     → Claude Vision (single call)               │ │
│  │ Audio     → ElevenLabs Scribe v1 transcription        │ │
│  │ URL       → Web Agent (agentic loop with tools)       │ │
│  │ YouTube   → youtube-transcript-api                    │ │
│  │ Text/DOCX → Direct parsing (python-docx, file read)   │ │
│  │ CSV       → pandas + Claude analysis                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Output: Standardized text with page markers                │
│  Format: === {TYPE} PAGE 1 of N ===                         │
└─────────────────────────────┬───────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. CHUNKING & EMBEDDING                     Status:         │
│                                              embedding       │
│  Parse page markers → Split into ~200 token chunks          │
│  → Clean text → OpenAI embedding (1536-dim)                 │
│  → Upsert to Pinecone (namespace = project_id)              │
│  → Save chunk files to Supabase Storage                     │
│                                                              │
│  Chunk ID: {source_id}_page_{N}_chunk_{M}                   │
│  Token counting: tiktoken (local, ~5% variance from Claude)  │
└─────────────────────────────┬───────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. SUMMARY GENERATION                       Status: ready   │
│                                                              │
│  Sample 8 distributed chunks → Claude Haiku → 150-200 token │
│  summary → Included in chat system prompt for quick context  │
└─────────────────────────────────────────────────────────────┘
```

### Chunking Configuration

```python
CHUNK_TOKEN_TARGET = 200    # Ideal chunk size
CHUNK_MARGIN_PERCENT = 20   # ±20% tolerance
CHUNK_MIN_TOKENS = 160      # Minimum viable chunk
CHUNK_MAX_TOKENS = 240      # Maximum chunk size
```

### Why Hybrid Token Counting?

| Method | Speed | Accuracy | Use Case |
|--------|-------|----------|----------|
| `tiktoken` (local) | ~10,000x faster | ~95% vs Claude | Chunking (called thousands of times) |
| Claude API | Network latency | Exact | Billing and quota checks |

---

## 5. Chat Agentic Loop

The chat service implements a **tool-use agentic loop** — Claude decides which tools to call, the system executes them, and results are fed back until Claude has enough information to respond.

### Flow

```
User Message
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  BUILD SYSTEM PROMPT (context_loader.py)                 │
│                                                          │
│  Base prompt (default_prompt.json)                       │
│  + Source context (available sources with IDs + summary) │
│  + User memory (global preferences)                     │
│  + Project memory (project-specific context)             │
│  + Brand context (tone/style guidelines)                 │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  TOOL USE LOOP (max 10 iterations)                       │
│                                                          │
│  Claude API call with tools:                             │
│  ├── search_sources (hybrid RAG search)                  │
│  ├── store_memory (persistent context)                   │
│  ├── studio_signal (trigger content generation)          │
│  ├── analyze_csv_agent (CSV data analysis)               │
│  ├── analyze_database_agent (live SQL queries)           │
│  └── Knowledge base tools (Jira, Notion - if configured) │
│                                                          │
│  Loop:                                                   │
│    Claude response → tool_use? ──Yes──▶ Execute tool     │
│         │                              │                 │
│         │                         Send tool_result       │
│         │                              │                 │
│         │                    Call Claude again ◀──────────┘
│         │                                                │
│         └── end_turn? ──Yes──▶ Extract text + citations  │
│                                Store assistant message    │
│                                Return to user            │
└─────────────────────────────────────────────────────────┘
```

### Hybrid Search Strategy (search_sources tool)

```
Source token count?
    │
    ├── < 1,000 tokens → Return ALL chunks (no search needed)
    │
    └── ≥ 1,000 tokens → Hybrid search:
         ├── 1. Keyword search (fuzzy matching, difflib, threshold 0.7)
         ├── 2. Semantic search (OpenAI embedding → Pinecone top-k=5)
         └── 3. Combine + deduplicate by chunk_id
```

### Citation System

- **Format**: `[[cite:CHUNK_ID]]` in Claude's response
- **Chunk ID**: `{source_id}_page_{page}_chunk_{n}`
- **Resolution**: Frontend parses → hover → `GET /citations/{chunk_id}` → tooltip with source name, page, and content

---

## 6. Source Processing Pipeline

### Processor Map

| Source Type | Processor | AI Method | Output |
|-------------|-----------|-----------|--------|
| PDF | `pdf_processor.py` | Claude Vision (batched, 5 pages/batch, parallel) | Real pages |
| PPTX | `pptx_processor.py` | Claude Vision (batched, same pattern as PDF) | Real slides |
| Image | `image_processor.py` | Claude Vision (single call per image) | 1 page per image |
| Audio | `audio_processor.py` | ElevenLabs Scribe v1 transcription | Single page |
| URL | `link_processor.py` | Web Agent (agentic loop with web_fetch/tavily) | Single page |
| YouTube | `youtube_processor.py` | youtube-transcript-api (no AI) | Single page |
| DOCX | `docx_processor.py` | python-docx (no AI) | Single page |
| Text | `text_processor.py` | Direct file read (no AI) | Single page |
| CSV | `csv_processor.py` | pandas + Claude analysis | Single page |
| Database | `database_processor.py` | Database analyzer agent | Single page |
| Research | `research_processor.py` | Deep research agent (web search) | Single page |

### Standardized Output Format

All processors produce the same format via `build_processed_output()`:

```
# Extracted from PDF document: quarterly_report.pdf
# Type: PDF
# Total pages: 25
# Processed at: 2024-01-15T10:30:00Z
# token_count: 15000
# ---

=== PDF PAGE 1 of 25 ===

[page content here]

=== PDF PAGE 2 of 25 ===

[page content here]
```

### Background Processing

- Uses `ThreadPoolExecutor` (4-80 workers based on tier)
- All processing is I/O-bound (API calls), not CPU-bound
- User gets immediate response, processing happens asynchronously
- Status tracked in Supabase `background_tasks` table
- Supports cancellation via cooperative pattern

---

## 7. Studio Content Generation

The Studio panel provides 18 AI-powered content generators organized by category.

### Studio Features

| Category | Feature | Description |
|----------|---------|-------------|
| **Learning** | Quiz | Interactive questions from sources |
| | Flash Cards | Memorization cards |
| | Audio Overview | TTS summary narration |
| | Mind Map | Hierarchical visualization |
| **Business** | Business Report | Data-driven insights |
| | Marketing Strategy | Growth planning |
| | PRD | Product requirements doc |
| | Infographic | Visual data representation |
| | Flow Diagram | Process visualization |
| | Wireframe | UI mockups |
| | Presentation | Slide deck generation |
| **Content** | Blog Post | Long-form articles |
| | Social Posts | LinkedIn/Instagram/X content |
| | Website | Landing page generation |
| | Email Templates | Marketing email drafts |
| | Components | UI component generation |
| | Ad Creative | Ad copy + visuals |
| | Video | Video script generation |

### Signal-Based Architecture

1. During chat, Claude emits `studio_signals` via the `studio_signal` tool
2. Signals appear as generation options in the Studio panel
3. User clicks a tool → if multiple signals, picker shown
4. Selected signal triggers backend generation job
5. Each feature has its own agent service + tool executor

---

## 8. Data Layer

### Supabase PostgreSQL Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | User accounts | email, password_hash, google_tokens, global_memory |
| `projects` | Project containers | name, user_id, costs (JSONB), custom_prompt |
| `sources` | Source metadata | type, status, embedding_info, summary_info |
| `chats` | Chat containers | title, selected_source_ids (JSONB) |
| `messages` | Chat messages | role, content (JSONB), metadata |
| `chunks` | RAG text chunks | source_id, text, chunk_id, page_number |
| `background_tasks` | Async task tracking | task_type, status, error_message |
| `brand_config` | Brand settings | colors, fonts, logos (JSONB) |

**Security**: Row-Level Security (RLS) policies ensure data isolation per user.

### Supabase S3 Storage Buckets

| Bucket | Purpose | Example Path |
|--------|---------|-------------|
| `raw-files` | Original uploads | `projects/{id}/sources/{id}/report.pdf` |
| `processed-files` | Extracted text | `projects/{id}/processed/{id}.txt` |
| `chunks` | Individual chunk files | `projects/{id}/chunks/{chunk_id}.txt` |
| `studio-outputs` | Generated content | `projects/{id}/studio/audio/overview.mp3` |
| `brand-assets` | Brand materials | `users/{id}/logos/logo.png` |

### Pinecone Vector Database

- **Model**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Index**: `growthxlearn` with cosine similarity
- **Namespace isolation**: One namespace per project
- **Metadata**: source_id, page_number, chunk_index, text

### Configuration Files

- **31 Prompt Configs** (`data/prompts/*.json`) — System prompts, model, temperature, max_tokens
- **70+ Tool Definitions** (`app/services/tools/**/*.json`) — Claude tool schemas for all features

---

## 9. External Integrations

### Integration Architecture

All integrations follow the same pattern:
1. **Lazy client initialization** (avoids errors if API key missing)
2. **Thin wrapper** (service layer handles orchestration)
3. **Cost tracking** (project_id passed to every API call)

| Service | Module | Purpose | Key Methods |
|---------|--------|---------|-------------|
| **Claude** | `integrations/claude/` | LLM + Vision | `send_message()`, `count_tokens()` |
| **OpenAI** | `integrations/openai/` | Embeddings | `create_embedding()`, `create_embeddings_batch()` |
| **Pinecone** | `integrations/pinecone/` | Vector search | `upsert_vectors()`, `search()`, `delete_by_source()` |
| **ElevenLabs** | `integrations/elevenlabs/` | Audio I/O | `transcribe()`, `text_to_speech()` |
| **Google** | `integrations/google/` | Drive + Imagen | OAuth flow, `list_files()`, `import_file()` |
| **Tavily** | `integrations/tavily/` | Web search | `search()` (fallback for web agent) |
| **Supabase** | `integrations/supabase/` | DB + Storage + Auth | PostgREST CRUD, S3 operations, JWT |
| **Jira** | `integrations/knowledge_bases/jira/` | Issue tracking | `search_issues()`, `get_issue()` |
| **Notion** | `integrations/knowledge_bases/notion/` | Knowledge base | `search()`, `read_page()` |

### Claude API Response Flow

```
claude_service.py          → Raw API call, returns {content_blocks, stop_reason, usage}
        ↓
claude_parsing_utils.py    → Parse response type:
  ├── is_tool_use()        → Extract tool calls, execute, loop back
  ├── is_end_turn()        → Extract text, store, return
  └── extract_citations()  → Parse web_search citations
        ↓
message_service.py         → Store messages in Supabase
```

---

## 10. Infrastructure & Deployment

### Development (Local)

```bash
bin/setup              # Create venv, install all deps
bin/dev                # Start backend (5001) + frontend (5173)
bin/dev --backend-only # Flask only
bin/dev --frontend-only # Vite only
```

### Docker (Self-Hosted Supabase)

```bash
cd docker && ./setup.sh    # One-command setup for everything
```

**19 Containers Total**:
- 3 NoobBook: backend (Flask:5001), frontend (nginx:80), migrate (one-time)
- 16 Supabase: PostgreSQL, Kong, Auth, REST, Storage, MinIO, Studio, Realtime, Analytics, Edge Functions, Imgproxy, Pooler, Meta, Vector

### Production (AWS EC2)

```
GitHub push to develop
    ↓
.github/workflows/deploy.yml
    ├── SSH into EC2
    ├── git pull
    ├── Run migrations
    ├── Rebuild + force-recreate containers
    ├── Health checks (40 retries × 3s)
    └── Verify deployed SHA
```

### Tier Configuration

| Tier | Workers | Pages/min | Use Case |
|------|---------|-----------|----------|
| 1 | 4 | 10 | Free tier |
| 2 | 16 | 100 | Standard |
| 3 | 24 | 200 | Pro |
| 4 | 80 | 1500 | Enterprise |

---

## 11. Key Design Patterns

### 1. Separation of Concerns

```
claude_service.py      → API calls only (no parsing, no storage)
claude_parsing_utils.py → Response parsing only (no API, no storage)
message_service.py     → CRUD only (no AI, no parsing)
tool_executors/        → Tool execution only (no orchestration)
```

### 2. AI Service Standard Pattern

Every AI service follows the same template:
1. **Load config** — `prompt_loader`, `tool_loader`, `tier_loader`
2. **Get paths** — `path_utils` functions
3. **Call API** — `claude_service.send_message()` with project_id
4. **Parse response** — `claude_parsing_utils.*` functions
5. **Return structured data**

### 3. Tool-Based Extraction

All document extraction uses Claude tools (force `tool_choice`) for structured output. This ensures per-page results and solves page boundary problems.

### 4. Lazy Initialization

All external API clients are initialized on first use, not at import time. This prevents startup errors when optional API keys are missing.

### 5. Centralized Configuration

- **Prompts**: 31 JSON files, loaded by `prompt_loader.py`
- **Tools**: 70+ JSON schemas, loaded by `tool_loader.py`
- **Tiers**: Rate limits in `tier_loader.py`, set via `ANTHROPIC_TIER` env var
- **Never hardcode** paths, prompts, or tool definitions inline

### 6. Background Processing

ThreadPoolExecutor handles I/O-bound tasks (API calls release Python's GIL):
- Source processing runs while user continues chatting
- Chat auto-naming happens after first message
- Memory merging runs in background (non-blocking)

### 7. Cost Tracking

Every Claude/OpenAI API call includes `project_id` for per-project cost tracking:
- Sonnet: $3/$15 per 1M input/output tokens
- Haiku: $1/$5 per 1M input/output tokens
- Costs stored as JSONB in project metadata

---

## Request Lifecycle Example

**User asks**: "What does the quarterly report say about revenue?"

```
1. POST /projects/{id}/chats/{id}/messages
   Body: { "message": "What does the quarterly report say about revenue?" }

2. main_chat_service.send_message()
   ├── Store user message in Supabase
   ├── Build system prompt (base + sources + memory)
   ├── Load message history
   └── Call Claude with tools [search_sources, store_memory, ...]

3. Claude responds: tool_use → search_sources
   ├── source_id: "abc-123" (the PDF)
   ├── keywords: ["revenue", "quarterly"]
   ├── query: "revenue figures from quarterly report"

4. source_search_executor.execute()
   ├── Source has 15,000 tokens → hybrid search
   ├── Keyword search: fuzzy match "revenue" in chunks
   ├── Semantic search: embed query → Pinecone top-5
   ├── Combine + dedupe → return 5 best chunks

5. Tool result sent back to Claude

6. Claude responds: end_turn
   "According to the quarterly report, revenue increased 40%
    year-over-year to $12.3M [[cite:abc-123_page_5_chunk_2]],
    driven primarily by the enterprise segment
    [[cite:abc-123_page_8_chunk_1]]."

7. Store assistant message → return to frontend

8. Frontend renders: markdown + citation badges
   User hovers [1] → GET /citations/abc-123_page_5_chunk_2
   → Tooltip: "Quarterly Report - Page 5" + chunk content
```
