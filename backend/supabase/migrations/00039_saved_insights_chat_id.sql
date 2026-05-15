-- Migration: add chat_id to saved_insights for same-chat refresh.
-- Created: 2026-05-16
--
-- Until now every refresh spawned a fresh chat which produced a noisy
-- chat list and lost the visual history of how an answer evolved.
-- Switching to a stable chat per insight means each refresh appends a
-- new turn to the same conversation; users can scroll to see the same
-- question answered over weeks. The column is nullable so legacy rows
-- created before this migration keep working — refresh falls back to
-- creating a chat the first time it runs and persists that chat_id
-- onto the row.

ALTER TABLE saved_insights
  ADD COLUMN IF NOT EXISTS chat_id UUID;

CREATE INDEX IF NOT EXISTS saved_insights_chat_id_idx
  ON saved_insights(chat_id)
  WHERE chat_id IS NOT NULL;

COMMENT ON COLUMN saved_insights.chat_id IS
  'Chat this insight refreshes into. NULL means refresh will lazily create one and write it back here.';
