# PM-AI Bot Roadmap

| # | Status | Improvement | Notes |
|---|--------|-------------|-------|
| 1 | ✅ | **Haiku movement** | Shipped — admin model selector lets you switch any category (chat/studio/query/extraction) to Haiku globally |
| 2 | ⬜ | **JIRA connection** | JIRA integration for querying tickets as a source |
| 3 | ✅ | **Usage credit limit for individual users** | Shipped — per-user $ limits with daily/weekly/monthly reset, progress bars in Team table + Chat header + Profile |
| 4 | ✅ | **STT** | Shipped — ElevenLabs real-time speech-to-text integrated in chat input |
| 5 | ⬜ | **4XX error fix for number of iterations** | Retry/handle 4XX errors inside agent loops instead of hard-failing |
| 6 | ✅ | **Chat download as PDF** | Shipped in a7c3fc8 — jspdf + html2canvas export |
| 7 | ✅ | **Chat-wise token utilisation** | Shipped — per-chat cost badge in ChatHeader + Opus row added to project breakdown |
| 8 | ✅ | **Opik logs — thread & unique user info** | Shipped — user_id, project_id, chat_id (thread_id), and tags attached to every trace |
| 9 | ✅ | **Studio Business & Product section bug** | Shipped — fire-and-forget triggerGeneration + DB source fallback + mermaid sanitization |
| 10 | ✅ | **Ledger DB** | Shipped — database connections support PostgreSQL/MySQL as sources with live SQL query agent |
| 11 | ⬜ | **Mixpanel MCP connection** | MCP server integration for Mixpanel analytics |
