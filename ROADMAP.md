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
