-- Migration: per-chat share scope
-- Description: Add an optional chat_id column to project_shares so a
--              share link can be scoped to a single chat instead of the
--              entire project's chat list. NULL keeps the historical
--              project-wide behaviour — every existing row stays project-
--              scoped, which is exactly what the owner intended at the
--              time they created the link.
-- Created: 2026-05-25

ALTER TABLE project_shares
  ADD COLUMN IF NOT EXISTS chat_id UUID
    REFERENCES chats(id) ON DELETE CASCADE;
-- ON DELETE CASCADE: if the owner deletes the chat, the per-chat share
-- becomes meaningless — a viewer hitting the link would 404 the only
-- chat in the scope. Removing the row is cleaner than leaving an
-- orphan that always errors. Project-wide shares (chat_id IS NULL)
-- are unaffected.

-- Hot lookup pattern is still "by token" (already covered by
-- project_shares_non_revoked_token_idx from migration 00021). The
-- per-chat scope check is a single column read on the already-loaded
-- row, so no new index is needed for the viewer path.
--
-- A secondary lookup the owner UI uses is "list shares for chat X" —
-- expected to be tiny per chat (a handful of links at most), so we
-- skip an index here too. Add one only if the row count justifies it.

COMMENT ON COLUMN project_shares.chat_id IS
  'Optional: when set, the share is scoped to this single chat instead of every chat in the project. NULL means project-wide.';
