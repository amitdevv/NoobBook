## Smooth UX Refactor for Refresh Churn

### Summary
Refactor the app’s async state flow so mutations patch existing UI state instead of blanking and reloading whole sections. Keep the current layouts, routes, and user-facing behavior unchanged; the work is internal and aimed at removing full-section spinners, post-action remounts, redundant refetches, and delayed “catch-up” refreshes.

### Implementation Changes
- **Settings and brand areas: stop remount-driven fetch churn**
  - Convert settings tabs in [AppSettings.tsx](/Users/adityagarud/Developer/NoobBook/frontend/src/components/dashboard/AppSettings.tsx) to a keep-alive pattern: once a section is opened, keep it mounted and hide it instead of unmounting it. Do the same for `DesignSection` sub-tabs.
  - Split each section’s loading into `initialLoad` vs `mutationInFlight`; only show skeleton/spinner on first hydrate. After that, keep existing content rendered and show row/button-level pending states.
  - Replace mutation-time full refetches with local reconciliation wherever APIs already return updated entities:
    - `ApiKeysSection`: keep the edited field rendered after save/delete; do not call `loadApiKeys()` after each key save. Update only the affected key locally and silently refresh once after the batch if needed.
    - `IntegrationsSection`: for DB/MCP create/delete/toggle, insert/remove/patch the returned item in local arrays instead of re-running `loadDatabases()` / `loadMcpConnections()` with section-wide spinners.
    - Brand sections (`Colors`, `Typography`, `Guidelines`, `Features`, asset sections): hydrate brand config once per settings session and reuse it across sub-tabs; saves update local state and success indicators only.
  - Reuse account-level integration data between Settings and Add Sources flows so `DatabaseTab`, `McpTab`, and Google status do not refetch separate copies of the same connection state.

- **Chat response flow: remove broad post-send refreshes**
  - Refactor [ChatPanel.tsx](/Users/adityagarud/Developer/NoobBook/frontend/src/components/chat/ChatPanel.tsx) so a completed AI response updates only the active chat, chat list entry, costs, usage, and studio signals that actually changed.
  - Remove the current post-send cascade of `loadChats()`, `loadUserUsage()`, and the two delayed `getChat()` calls. Replace it with:
    - immediate local patch from the streamed canonical user message and final assistant message,
    - one silent metadata reconciliation only if the stream did not provide enough state,
    - no component-level `loading` flip after a send.
  - Extend the stream contract from [routes.py](/Users/adityagarud/Developer/NoobBook/backend/app/api/messages/routes.py) / [main_chat_service.py](/Users/adityagarud/Developer/NoobBook/backend/app/services/chat_services/main_chat_service.py) so the terminal event includes the assistant message plus sync payload needed by the UI:
    - updated chat metadata,
    - current studio signals,
    - chat cost snapshot,
    - current user usage snapshot.
  - Keep chat auto-naming asynchronous, but stop the fixed `1s`/`4s` timeout fetches. Use a silent metadata reconciliation tied to task completion instead of hardcoded timers.

- **Workspace lists: mutate rows, not sections**
  - In [SourcesPanel.tsx](/Users/adityagarud/Developer/NoobBook/frontend/src/components/sources/SourcesPanel.tsx), keep `loadSources()` for first load only. For upload/add/delete/rename/retry/cancel:
    - use returned `source` objects to insert/update rows locally,
    - use silent polling only for processing-state transitions,
    - never flip the whole panel back to `loading=true` after a single row action.
  - Preserve the existing optimistic per-chat source selection flow, but make every other source mutation follow the same pattern.
  - Keep `refreshSources()` as the only polling path; do not reuse the initial-load spinner path for background updates.

- **Studio: remove N-per-section bootstrap fetches**
  - Replace the current “every section fetches its own saved jobs on mount” pattern with one shared studio jobs store.
  - Add one grouped backend read endpoint over `studio_jobs` and hydrate Studio once when the panel first expands; existing per-tool generate/poll/delete endpoints stay unchanged.
  - Refactor Studio sections/hooks to read/write the shared store instead of each calling `listJobs()` on mount. Generating a new job should append/update only that job type in the shared store, not trigger unrelated section work.
  - Preserve current polling behavior for in-progress jobs, but scope it to the active job type only.

- **Cross-cutting async rules**
  - Standardize on one repo-wide rule: initial view loads may block, mutations may not. Mutations use optimistic or in-place updates plus silent reconciliation.
  - Introduce small shared helpers/hooks for resource state (`hydrate`, `patchOne`, `insertOne`, `removeOne`, `silentRefresh`) instead of hand-written `load*()` loops in each section.
  - Keep all existing public routes and visible UI unchanged; no schema migrations.

### Internal Interface Changes
- Extend chat stream terminal payload to carry sync metadata needed by the current view.
- Add a grouped studio jobs read endpoint so Studio can hydrate once instead of fan-out fetching per section.
- Add task target metadata to the active-tasks payload if needed so chat-title reconciliation can key off completed `chat_naming` work without polling arbitrary chat records.

### Test Plan
- `frontend`: `npm run lint` and `npm run build`.
- `backend`: `pytest`.
- Manual regression matrix:
  - API Keys: save 3 keys in sequence without the section blanking or losing field state.
  - Integrations: create/delete DB and MCP connections without section-wide spinner resets.
  - Design tabs: switch between Colors/Typography/Guidelines/Features without reloading or losing unsaved drafts.
  - Chat: send a message and verify only message/cost/usage/title metadata updates, with no full chat skeleton flash and no delayed “catch-up” reloads.
  - Sources: upload/add/delete/rename/retry/cancel while keeping the list visible and stable.
  - Studio: expanding the panel should hydrate once; generating content should update only the relevant tool section.
  - Auth/RBAC: token refresh, admin-only sections, and permissions-gated tools still behave exactly as before.

### Assumptions
- “No front-end or back-end changes” means no visible UX redesign and no product behavior change; internal state-management and API-plumbing changes are allowed.
- The refactor is a single broad pass, but acceptance is based on eliminating blocking refresh behavior, not on introducing a new state-management library.
- Existing REST endpoints remain the source of truth; only narrow internal payload additions are allowed where the current frontend cannot avoid redundant refetching.
