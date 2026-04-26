# PM-AI Bot Roadmap

| # | Status | Improvement | Notes |
|---|--------|-------------|-------|
| 1 | ✅ | **Haiku movement** | Shipped — admin model selector lets you switch any category (chat/studio/query/extraction) to Haiku globally |
| 2 | ✅ | **JIRA connection** | Shipped — 4 live chat tools (list_projects, search_issues, get_issue, get_project) + API key settings UI |
| 3 | ✅ | **Usage credit limit for individual users** | Shipped — per-user $ limits with daily/weekly/monthly reset, progress bars in Team table + Chat header + Profile |
| 4 | ✅ | **STT** | Shipped — ElevenLabs real-time speech-to-text integrated in chat input |
| 5 | ✅ | **4XX error fix for number of iterations** | Shipped — centralized retry in claude_service with exponential backoff (429/529: 30s×attempt, 500s: 2^attempt×2s) |
| 6 | ✅ | **Chat download as PDF** | Shipped in a7c3fc8 — jspdf + html2canvas export |
| 7 | ✅ | **Chat-wise token utilisation** | Shipped — per-chat cost badge in ChatHeader + Opus row added to project breakdown |
| 8 | ✅ | **Opik logs — thread & unique user info** | Shipped — user_id, project_id, chat_id (thread_id), and tags attached to every trace |
| 9 | ✅ | **Studio Business & Product section bug** | Shipped — fire-and-forget triggerGeneration + DB source fallback + mermaid sanitization |
| 10 | ✅ | **Ledger DB** | Shipped — database connections support PostgreSQL/MySQL as sources with live SQL query agent |
| 11 | ✅ | **Mixpanel MCP connection** | Shipped — Mixpanel as a project-scoped source with live Query API tools (list_events, query_events, segmentation, funnels, retention, JQL). See [plan.md](plan.md) for the Option A vs Option B tradeoff and the clean-replacement migration path if we move to hosted MCP + OAuth later. |
| 12 | ⬜ | **Stitch / design.md in admin settings** | Editable `design.md` spec per workspace (format from [google-labs-code/design.md](https://github.com/google-labs-code/design.md)) surfaced in Admin Settings → Design. Ship with a bundled sample. Feeds brand + studio generation so generated content follows the design system. |
| 13 | ✅ | **GPT Image 2 for image generation** | Shipped — `gpt-image-2-2026-04-21` is the default for all studio image surfaces (ads, social, infographics, blog, email, website) via `client.images.generate` / `client.images.edit` (brand-logo path). Streams partial frames into a live `<PartialImagesPreview>` strip on every progress indicator. Falls back to Gemini on model-not-found/unauthorized errors. Per-image cost tracked under `projects.costs.images`. |
| 14 | ⬜ | **Replace Paste with document editor + richer preview** | Swap the raw "Paste text" source for a Notion-style block editor (headings, lists, links, embeds). Upgrade the document preview modal (clicking any uploaded doc) with proper page navigation, search, and format-faithful rendering. |
| 15 | ⬜ | **Share project** | Shareable project links that expose chats only — sources, API keys, and memory stay with the owner. Collaborators get read-only chat access; options for public-link vs invited-user modes. |
| 16 | ⬜ | **Admin-editable system prompts with protected variables** | Admin Settings surface for all prompt configs (`default_prompt`, `pdf_extraction_prompt`, `memory_prompt`, etc.). Body is editable; required variable slots (`{today}`, `{project_memory}`, `{sources}`, etc.) render as locked chips that cannot be removed or renamed. Save validates that every required slot is still present. |
| 17 | ⬜ | **Reduce API costs** | Audit + plan: prompt-caching coverage gaps, Haiku downgrades for non-critical paths (summaries, auto-naming, chunk extraction), batch API (50% off) for async studio jobs, output-token caps, streaming-vs-non-streaming trade-offs. Output: cost report with 3–5 shippable follow-up PRs. |
