-- Migration: chats.user_stopped_at — durable user-stop signal for SSE streams.
-- Created: 2026-05-18
--
-- Background: §2.1 introduced a way to distinguish "user clicked Stop" from
-- "proxy idle-timeout closed the connection" so the assistant response no
-- longer gets the false-positive "(stopped by user)" label. The initial
-- implementation used an in-process `_user_stopped_chats` set in
-- `app/api/messages/routes.py`. Code review (H2) flagged that this breaks
-- the moment gunicorn runs more than one worker — POST /messages/stop and
-- the SSE GeneratorExit can land on different workers, so the marker is
-- invisible to the worker that needs to read it. The uncommitted
-- gunicorn.conf.py change on this branch raises workers to 4, making this
-- imminent.
--
-- This migration replaces the per-process set with a single column on
-- `chats`. The SSE worker's GeneratorExit handler reads
-- `user_stopped_at` and only treats the close as a user-initiated stop
-- when the timestamp is fresher than the stream's start time. That
-- "freshness window" defeats the M1 race where a late-arriving /stop
-- POST would otherwise leak its marker into the chat's next message.
--
-- Default NULL is required: existing chats stay untouched and the SELECT
-- on the GeneratorExit path returns NULL → treated as "no user stop"
-- (matches the pre-feature behaviour exactly).

ALTER TABLE chats
  ADD COLUMN IF NOT EXISTS user_stopped_at TIMESTAMPTZ DEFAULT NULL;

COMMENT ON COLUMN chats.user_stopped_at IS
  'Last time the user clicked Stop on this chat (POST /messages/stop). The SSE worker compares this against its own stream-start time on GeneratorExit; a fresher timestamp means the user really did click Stop and the assistant message should be labeled accordingly. Older timestamps are ignored — they refer to a previous message and never apply to the current stream.';
