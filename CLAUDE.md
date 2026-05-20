# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository. Keep this file lean — it's loaded into every session's context window. Deep details belong in code comments next to the thing they document.

---

## What NoobBook is

Open-source NotebookLM alternative. React frontend + Flask backend, self-hosted Supabase for data + storage + auth. Website: [noobbooklm.com](https://noobbooklm.com).

**Two views, that's it:**
1. **Dashboard** — project list (create / open / delete) + course resources.
2. **Project Workspace** — three panels: Sources (multi-modal ingestion) · Chat (RAG Q&A with citations + voice) · Studio (content generation — fully built, not "planned").

---

## Run / build

```bash
bin/setup                  # First-time: venv + deps for backend & frontend
bin/dev                    # Start both servers (backend :5001, vite :5173)
bin/dev --backend-only
bin/dev --frontend-only
bin/dev --install          # Refresh deps before starting

cd frontend && npm run build   # Production frontend build
cd frontend && npm run lint    # ESLint
cd backend && pytest           # Backend tests (372+ currently)
```

**System deps:** `libreoffice` and `ffmpeg` (audio + DOCX/PPTX paths). On macOS: `brew install libreoffice ffmpeg`.

**Docker / self-hosted Supabase:** see `docker/MAC_SETUP.md`. 16 containers (Supabase stack + backend + frontend + migrate).

**Production:** Coolify behind Traefik on a bare-metal IOFlood box. The production compose file is `docker-compose-dev.yml` (NOT `docker-compose.yml`, which is the local-dev stack).

---

## Env vars

Create `backend/.env`. Minimum:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...

# Supabase
SUPABASE_URL=http://kong:8000             # internal Docker hostname in prod
SUPABASE_PUBLIC_URL=https://<your-host>   # browser-reachable host — REQUIRED in prod
                                          # so signed storage URLs work
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
JWT_SECRET=...                            # needed for signature-verified fail-open

# Per-feature (optional)
ELEVENLABS_API_KEY=...      # Audio / voice transcription
TAVILY_API_KEY=...          # Web search fallback
GOOGLE_CLIENT_ID=...        # Google Drive import (+ SECRET)
NOTION_API_KEY=...
FRESHDESK_API_KEY=...       # + FRESHDESK_DOMAIN
JIRA_CLOUD_ID=...           # + JIRA_EMAIL, JIRA_API_KEY
MIXPANEL_SERVICE_ACCOUNT_USERNAME=...   # + SECRET + PROJECT_ID + REGION (us|eu|in)
ANTHROPIC_TIER=1            # 1-4, controls worker count + rate limits
```

API keys are also editable from Settings → API Keys (writes to `.env` via `app/api/settings/api_keys.py` :: `API_KEYS_CONFIG`). Services with cached config (Notion, Jira, Mixpanel) must call `reload_config()` in `update_api_keys()` after `env_service.reload_env()` for changes to take effect without a restart.

---

## Claude model

**Default: `claude-sonnet-4-6`** (no date suffix). Haiku 4.5 is `claude-haiku-4-5-20251001`. Opus 4.6 is `claude-opus-4-6` (rare — only `website_agent`, `component_agent`, `presentation_agent`).

Models are configured per-prompt in `data/prompts/*_prompt.json`. Hardcoded fallbacks in agents should also be `claude-sonnet-4-6`. Pricing snapshot: Sonnet $3 / $15 per MTok, Haiku $1 / $5, Opus $5 / $25.

---

## Code rules (the important ones)

1. **DRY.** Extract repeated logic. The DB-style analyzer agents (Freshdesk, Mixpanel) all mirror the same pattern — when adding a new one, copy don't reinvent.
2. **One thing per file when it exceeds ~100 lines.** Keeps blast radius small.
3. **Comments explain WHY, not WHAT.** Especially around LLM choices, prompt engineering, rate limits, and any non-obvious workaround. Don't write comments that just paraphrase the code.
4. **Type hints on every Python function** (params + return). PEP 8 throughout.
5. **Icons: Phosphor (`@phosphor-icons/react`)**, never Lucide.
6. **Styling: Tailwind only.** No inline styles, no `.css` files unless absolutely required.
7. **Components: shadcn/ui first.** `npx shadcn@latest add <name>` before building anything custom. See `frontend/DESIGN_SYSTEM.md` for colors (Amber-600 primary, Stone-800 text, warm-cream bg).
8. **Toasts:** custom hook at `./ui/toast`, not `../hooks/use-toast`.
9. **When unclear — ask.** Don't guess at architectural decisions.

---

## Layout map

```
backend/
  app/
    api/                    Flask blueprints — routes only, no business logic
      chats, messages, projects, sources, settings, citations,
      google, transcription, mcp, insights, logs, ...
    services/
      ai_agents/            Agentic loops (multi-turn tool use)
                              freshdesk_analyzer_agent, mixpanel_analyzer_agent,
                              csv_analyzer_agent, database_analyzer_agent,
                              web_agent_service, deep_research_agent
      ai_services/          Single-call AI tasks (no loop): pdf, pptx, image
      chat_services/        main_chat_service.py — RAG + tool dispatch
      data_services/        Pure CRUD over Supabase (chat, message, project,
                              brand_asset, user, share, insight, ...)
      tool_executors/       Tool dispatch + execution surfaces for agents
      tools/                JSON tool definitions for Claude
        chat_tools/         Tools the main chat exposes (search, memory,
                              analyze_*_agent triggers, mcp shims)
        <agent>_agent/      Sub-tools loaded by a specific analyzer agent
        web_agent/, pdf_tools/, pptx_tools/, image_tools/
      integrations/
        claude/             Anthropic SDK wrapper (cost tracking, Opik)
        supabase/           auth_service, storage_service, supabase_client,
                              signed-URL rewrite for browser-reachable hosts
        knowledge_bases/    jira, mixpanel, notion service modules
        mcp/                MCP client + tool registry (per-user)
        elevenlabs/, google/, freshdesk/, youtube/
      source_services/      Ingestion pipeline (upload + processing per type)
      studio_services/      One module per studio item type
      background_services/  task_service, insight_scheduler, log_housekeeping
    config/
      prompt_loader.py      Loads & merges per-project prompt overrides
      tool_loader.py        load_tool / load_tools_from_category
      prompt_referenced_by.py   Maps prompt name → code file (UI breadcrumb)
      tier_loader.py        ANTHROPIC_TIER → workers + RPM
      context_loader.py     Builds chat system prompt (sources + memory)
      brand_context_loader.py   Brand snippet injection
    utils/
      auth_middleware.py    JWT verify (fast-path local + slow-path GoTrue)
      claude_parsing_utils.py   Tool-use parsing helpers
      path_utils.py         All directory access — never hardcode paths
      rate_limit_utils.py, batching_utils.py, encoding_utils.py
      text/                 chunking, page_markers, processed_output, cleaning
  data/
    prompts/                *_prompt.json — every editable system prompt
    projects/{id}/agents/   Debug logs for agent runs (optional)
  supabase/migrations/      Sequentially-numbered SQL migrations
  tests/

frontend/
  src/
    components/
      chat/                 ChatPanel, ChatMessages, ChatInput, citations
      sources/              SourcesPanel + per-type tabs (Drive, Notion,
                              Freshdesk, Jira, Mixpanel, plain upload)
      studio/               StudioPanel + sections, viewers, saved insights
      project/              ProjectHeader, ProjectWorkspace, settings dialogs
      settings/sections/    Per-area settings: ApiKeys, Prompts, Models,
                              Permissions, Logs, Profile, Team, ...
      dashboard/, onboarding/, ui/
    lib/api/                Typed API clients (chats, sources, insights, ...)
    contexts/, hooks/
```

---

## Data layer

### Supabase tables (Postgres + RLS per user)

| Table | Purpose |
|---|---|
| `users` | Accounts, global memory, settings, `google_tokens`, permissions |
| `projects` | Metadata, custom prompts, `costs`, project memory, brand config |
| `sources` | Source rows; `embedding_info` carries type/ext metadata |
| `chats` | Containers; `selected_source_ids` for per-chat source scoping |
| `messages` | JSONB `content` — string, dict `{text}`, or list of typed blocks |
| `chunks` | RAG text chunks with `chunk_id = {source_id}_page_{n}_chunk_{n}` |
| `studio_signals` | AI-emitted intents that drive studio generators |
| `background_tasks` | Async task tracking |
| `brand_assets`, `brand_config` | Brand identity per project |
| `saved_insights` | Pinned chat answers with optional auto-refresh |
| `freshdesk_tickets` | Synced ticket mirror used by the Freshdesk agent |
| `oauth_state_nonces` | OAuth state CSRF token store |
| `app_settings_api_keys` | Encrypted runtime API-key overrides |

### Supabase Storage buckets

| Bucket | Purpose |
|---|---|
| `raw-files` | Originals (PDF, DOCX, images, audio) |
| `processed-files` | Extracted text per source |
| `chunks` | Chunked text for RAG (also indexed in Pinecone) |
| `studio-outputs` | Generated audio / video / PDFs |
| `brand-assets` | Logos, icons, fonts |
| `chat-attachments` | Inline images pasted/dropped into chat |

### Signed-URL host rewriting

`storage_service._rewrite_signed_url_for_browser` swaps the internal Supabase host (`SUPABASE_URL`, typically `http://kong:8000` in Docker) for a browser-reachable one. **Self-hosted deployments must set `SUPABASE_PUBLIC_URL`** to their public origin — otherwise screenshots, PDFs, audio, and brand assets render broken. `X-Forwarded-Host` is intentionally NOT trusted (spoofable when the backend is reachable directly).

---

## API surface

Base URL: `http://localhost:5001/api/v1` (local) / `http://localhost/api/v1` (Docker) / `https://<host>/api/v1` (prod).

Read the routes inline — `backend/app/api/<area>/routes.py`. Key surfaces:

- **Projects:** `GET/POST /projects`, `GET/PUT/DELETE /projects/{id}`, `/costs`, `/memory`
- **Chats:** `GET/POST /projects/{id}/chats`, `/chats/{cid}` (GET/PUT/DELETE), `/messages`, `/messages/stream` (SSE), `/prompt`
- **Sources:** `GET/POST /projects/{id}/sources`, `/url`, `/text`, per-source `PUT/DELETE/cancel/retry`
- **Settings:** `/settings/api-keys`, `/settings/prompts` (admin), `/settings/users/me/{usage,permissions}`
- **Auth helpers:** `/auth/me`, `/auth/logout`, `/google/{status,auth,callback,disconnect}`
- **Citations:** `GET /projects/{id}/citations/{chunk_id}` — chunk content for tooltip

---

## Key architectural patterns

### Source ingestion pipeline

`uploaded → processing → [embedding if token_count > 2500] → ready`. Raw files preserved on error so retry doesn't re-upload. Processing runs in background threads. Output format is uniform across types — built by `build_processed_output()` in `app/utils/text/processed_output.py` with `=== {TYPE} PAGE n of N ===` markers. Token-based chunking (~200 tokens via tiktoken `cl100k_base` for speed) handles all splitting.

Per-type extractor:

| Type | Service | AI? |
|---|---|---|
| PDF | `ai_services/pdf_service.py` | Batched vision, 5 pages/batch, parallel |
| PPTX | `ai_services/pptx_service.py` | Same shape as PDF (slides as images) |
| Image | `ai_services/image_service.py` | Single Claude vision call |
| DOCX | `utils/docx_utils.py` | python-docx, no AI |
| Audio | `integrations/elevenlabs/audio_service.py` | ElevenLabs Scribe v1 |
| Text | `source_processing_service.py` | Direct read |
| YouTube | `integrations/youtube/youtube_service.py` | youtube-transcript-api |
| URL | `ai_agents/web_agent_service.py` | Agentic loop (web_fetch + tavily) |
| Notion / Freshdesk / Jira / Mixpanel | per-integration syncs | Service-account based |

### Main chat (RAG agentic loop)

`main_chat_service.send_message`:

```
user message → Claude (with tools) → tool_use? → execute → loop
                                   → end_turn → store + return
```

System prompt assembled at request time by `context_loader.build_full_context` (sources, memory) + `brand_context_loader` (brand identity). Per-chat source selection via `chats.selected_source_ids`.

**Citations** use chunk IDs, not source IDs: `[[cite:{source_id}_page_{n}_chunk_{m}]]`. Frontend parses the marker and fetches chunk content via `/citations/{chunk_id}` on hover.

**Image attachments** in user messages persist as a list of typed blocks:
`[{type:"image", storage_path, media_type, filename}, {type:"text", text:"..."}]`
The image block is dropped from `messages.content` on the read path *only* for tool-chain intermediates (`tool_use` / `tool_result`) — user image content is kept and re-signed by `message_service._format_blocks_with_images`. See `chat_service._is_displayable_message`.

### Analyzer-agent pattern (Freshdesk / Mixpanel mirror)

When an integration needs more than a couple of read-only tool calls, wrap it in an analyzer agent so the main chat sees ONE tool instead of many.

```
backend/data/prompts/<name>_analyzer_agent_prompt.json
  ↳ auto-appears in admin Settings → Prompts → "Agents" category
    (filename ending in _analyzer_agent triggers the rule in
     frontend/src/components/settings/sections/promptsLib.ts)

backend/app/services/ai_agents/<name>_analyzer_agent.py
  ↳ singleton; .run(project_id, source_id, query, chat_id, user_id, on_event)
  ↳ tool_loader.load_tools_from_category("<name>_agent")
  ↳ loop up to MAX_ITERATIONS (40), terminate on return_<name>_analysis
  ↳ MAX_TOOL_RESULT_CHARS cap on per-call payload (avoids context blow-up)

backend/app/services/tool_executors/<name>_analyzer_agent_executor.py
  ↳ formats {summary, findings[], recommendations[]} into chat-ready markdown

backend/app/services/tools/chat_tools/analyze_<name>_agent_tool.json
  ↳ trigger tool the main chat sees (source_id + query)

backend/app/services/tools/<name>_agent/*.json
  ↳ all sub-tools live here; never expose to main chat

backend/app/services/chat_services/main_chat_service.py
  ↳ self._get_<name>_analyzer_tool() in __init__ cache + _get_tools branch
  ↳ dispatch case in _execute_tool for "analyze_<name>_agent"
  ↳ permission gate: user_has_permission(user_id, "data_sources", "<name>")

backend/app/config/prompt_referenced_by.py
  ↳ one-line entry maps prompt → agent file (UI breadcrumb)
```

Freshdesk is the reference implementation; Mixpanel was the most recent mirror.

### MCP integration

`backend/app/services/integrations/mcp/` — supports stdio and SSE transports. Per-user tool registry merged into `_get_tools()` at request time. stdio commands are allowlist-validated; arbitrary subprocess execution is rejected. Use for third-party MCP servers (e.g. official Mixpanel MCP) without rewriting their tools.

### Saved insights

Pinned chat answers (`saved_insights` table). Optional auto-refresh (daily/weekly) is driven by `background_services/insight_scheduler.py` — re-runs the original query through the same chat history.

### Memory

Two scopes: user-global (`users.memory`) and project-scoped (`projects.memory`). Tool-based — Claude calls `store_memory` → tool returns immediately → background task uses Haiku to merge new + existing (cap 150 tokens) → next system prompt includes the merged result via `context_loader`.

---

## AI service standard pattern

Every AI service / agent / tool executor follows the same load-config → call → parse shape:

```python
prompt_config = prompt_loader.get_prompt_config("<service_name>")
tier_config   = get_anthropic_config()         # workers, RPM
tool_def      = tool_loader.load_tool("<category>", "<tool_name>")
output_dir    = path_utils.get_processed_dir(project_id)   # never hardcode

response = claude_service.send_message(
    messages=messages,
    system_prompt=prompt_config["system_prompt"],
    model=prompt_config["model"],
    max_tokens=prompt_config["max_tokens"],
    temperature=prompt_config["temperature"],
    tools=[tool_def],
    project_id=project_id,                     # required for cost tracking
)

# Parse only via claude_parsing_utils
is_tool_use(response) / is_end_turn(response)
extract_text(response) / extract_tool_use_blocks(response)
extract_tool_inputs(response, "<tool_name>")
build_tool_result_content(results)
```

**Never:**
- Hardcode paths — use `path_utils`.
- Parse Claude responses by hand — use `claude_parsing_utils`.
- Roll your own rate limiter / batcher — `RateLimiter` + `create_batches` exist.
- Skip `project_id` on Claude calls — cost tracking depends on it.

For batched / parallel work: `ThreadPoolExecutor(max_workers=tier_config["max_workers"])` with cooperative cancellation via `task_service.is_target_cancelled(source_id)`. `DEFAULT_BATCH_SIZE = 5`.

---

## Tier configuration

`ANTHROPIC_TIER` in `.env` (1–4) drives concurrency. From `app/config/tier_loader.py`:

| Tier | Workers | Pages/min | Use |
|---|---|---|---|
| 1 | 4 | 10 | Free |
| 2 | 16 | 100 | Standard |
| 3 | 24 | 200 | Pro |
| 4 | 80 | 1500 | Enterprise / demos |

PDF/PPTX is I/O-bound so high worker counts are fine; the practical ceiling is the output-token-per-minute limit, not the worker count.

---

## Web agent / deep research

`web_agent_service` runs Claude's agentic loop for URL ingestion. Tools split into:
- **Server tools** — Claude handles execution (`web_search`, `web_fetch`).
- **Client tools** — we execute via `web_agent_executor.py` (`tavily_search`).
- **Termination tool** — `return_search_result` signals "done".

Execution logs saved to `data/projects/{id}/agents/web_agent/{exec_id}.json` for postmortem. `deep_research_agent` uses the same skeleton with more iterations + file-staging tools.

---

## Cost tracking

Per-project, stored in `projects.costs` JSONB. Every `claude_service.send_message` call must thread `project_id`. Image gen costs tracked separately under `projects.costs.images`. ProjectHeader surface in the UI shows totals with a tooltip breakdown.

---

## Frontend specifics

- **Voice input** uses ElevenLabs realtime via a backend-issued single-use 15-min WebSocket token. PCM 16-bit base64 over AudioWorklet.
- **Google Drive import** uses OAuth 2.0 (`drive.readonly`); tokens stored per-user in `users.google_tokens`, auto-refresh on expiry. Workspace types export: Docs→DOCX, Sheets→CSV, Slides→PPTX. Callback URL is derived from request host + API prefix; override with `GOOGLE_REDIRECT_URI` if your reverse proxy needs it.
- **Chat auto-naming** runs in the background after the first message via Haiku; non-blocking.
- **Onboarding tour** lives in `components/onboarding/`; first-run 5-step coachmark.

---

## Conventions for new work

1. **New AI surface** → start by writing the prompt JSON in `data/prompts/`. The admin Prompts UI auto-discovers it. Categorisation in `frontend/src/components/settings/sections/promptsLib.ts` is name-based (`*_analyzer_agent` → Agents, `*_extraction` / `csv_processor` / `summary` → Extraction, `default` / `chat_naming` / `memory` → Chat, everything else → Studio).
2. **New tool for Claude** → JSON in `app/services/tools/<category>/`, loaded via `tool_loader`. If the tool is agent-internal, put it in the agent's subdir; if main-chat-visible, `chat_tools/`.
3. **New integration that needs an editable prompt** → mirror the Freshdesk / Mixpanel analyzer pattern. Don't expose raw integration tools to the main chat.
4. **New migration** → next sequential number in `backend/supabase/migrations/`. The migrate container applies them on boot. Mirror any filter logic in both the SQL and the Python helpers it represents (see `_is_displayable_message` ↔ `list_chats_with_message_count` RPC).
5. **New API key** → entry in `API_KEYS_CONFIG`, validator in `app/services/app_settings/validation/`, registered in `ValidationService`, routing in `_validate_key`. Frontend auto-renders.

---

## Gotchas worth remembering

- **`SUPABASE_PUBLIC_URL` MUST be set in prod** — without it, signed storage URLs point at `http://kong:8000` and the browser can't reach them. Symptom: screenshots vanish on refresh.
- **JWT fail-open requires `JWT_SECRET`** — if unset and GoTrue blips, the auth middleware fails closed (no more "trust the unverified `sub`" path). This is intentional security hardening.
- **`messages.content` shape varies** — string | dict `{text}` | list of typed blocks. Filters in `chat_service.get_chat` and `_is_displayable_message` must distinguish "tool-chain list" (skip) from "user image+text list" (keep).
- **Migration numbering can collide** when develop and main fork — check `ls backend/supabase/migrations/ | sort` before adding.
- **The `freshdesk_analyzer_agent` and `mixpanel_analyzer_agent` patterns are load-bearing examples** — if you're tempted to deviate, ask first.

---

## When stuck

- The repo has 372+ backend tests. Run the relevant slice (`pytest tests/test_chat_service.py -v`) before opening a PR.
- For any "where does X live?" question, prefer `grep` over guessing — file paths in this doc may drift between updates.
- For LLM behaviour questions, check the prompt JSON first — it's the source of truth.
- For "why did we do it this way?" — git log + commit messages tend to carry the rationale.
