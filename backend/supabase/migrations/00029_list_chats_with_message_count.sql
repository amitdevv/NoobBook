-- Migration: list_chats_with_message_count RPC
-- Description: Replace the N+1 fan-out in chat_service.list_chats() (one
--              count query per chat — 21 round-trips for 20 chats) with a
--              single RPC that joins chats to a filtered message count in
--              one query.
--
-- The Python filter (`_is_displayable_message` in chat_service.py) drops
-- messages that wouldn't show in the rendered transcript: non-user/
-- assistant roles, list-content rows (tool-chain envelopes), and rows
-- whose extracted text trims to empty. The SQL here mirrors that filter
-- so the sidebar count never drifts from what the chat header shows for
-- the same chat.
--
-- Indexes already cover (messages.chat_id) and (chats.project_id) per
-- the initial schema, so this is a pure round-trip-elimination win:
-- expected ~80-150ms saved on the chat sidebar for projects with 20+ chats.

CREATE OR REPLACE FUNCTION list_chats_with_message_count(p_project_id UUID)
RETURNS TABLE (
    id UUID,
    title TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    costs JSONB,
    message_count BIGINT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        c.id,
        c.title,
        c.created_at,
        c.updated_at,
        c.costs,
        COALESCE((
            SELECT COUNT(*)
            FROM messages m
            WHERE m.chat_id = c.id
              -- Mirror chat_service._is_displayable_message:
              -- 1. role must be user or assistant (skip system/tool roles)
              AND m.role IN ('user', 'assistant')
              -- 2. list-content rows are tool-chain intermediates (assistant
              --    tool_use envelopes + user tool_result wrappers); skip them
              AND jsonb_typeof(m.content) <> 'array'
              -- 3. text content (after stripping whitespace) must be non-empty
              AND (
                  -- string-typed JSONB: "hello"  →  trimmed text length > 0
                  (jsonb_typeof(m.content) = 'string'
                      AND length(btrim(m.content #>> '{}')) > 0)
                  -- object-typed JSONB: {"text":"hello"}  →  text field non-empty
                  OR (jsonb_typeof(m.content) = 'object'
                      AND length(btrim(COALESCE(m.content->>'text', ''))) > 0)
              )
        ), 0)::BIGINT AS message_count
    FROM chats c
    WHERE c.project_id = p_project_id
    ORDER BY c.updated_at DESC;
$$;

-- Allow PostgREST to expose this through the auto-generated /rpc API
-- so the Supabase Python SDK can call it via .rpc(...).execute().
GRANT EXECUTE ON FUNCTION list_chats_with_message_count(UUID) TO anon, authenticated, service_role;
