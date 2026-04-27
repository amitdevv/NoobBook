-- Migration: Project Shares (Roadmap #15)
-- Description: Read-only shareable links for projects. Owner generates a
--              token; viewers see chat list + full chats + citations +
--              studio output artifacts as read-only. Sources, memory,
--              API keys, brand config, and project-level costs stay
--              private. Two modes: public (anyone with the link) and
--              invited (logged-in user whose email matches a row in
--              invited_emails).
-- Created: 2026-04-27

-- ============================================================================
-- project_shares — one row per active or revoked share link
-- ============================================================================

CREATE TABLE IF NOT EXISTS project_shares (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  token TEXT NOT NULL UNIQUE,
  mode TEXT NOT NULL CHECK (mode IN ('public', 'invited')),
  invited_emails TEXT[] NOT NULL DEFAULT '{}',
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- NULL means the share never expires — owner can still revoke.
  expires_at TIMESTAMPTZ,
  -- Set when the owner revokes the link. Row is kept (audit trail) but
  -- the active-share check rejects it.
  revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS project_shares_project_id_idx
  ON project_shares (project_id);

-- Hot read: viewer hits /share/{token}/* and we look up by token. Already
-- UNIQUE which gives an index, but adding a partial index for active shares
-- keeps the lookup fast even with many revoked rows.
CREATE INDEX IF NOT EXISTS project_shares_active_token_idx
  ON project_shares (token)
  WHERE revoked_at IS NULL;

-- ============================================================================
-- chats — track fork lineage so the viewer's "continue in your workspace"
-- copy can show a "forked from project X" breadcrumb.
-- ============================================================================

ALTER TABLE chats
  ADD COLUMN IF NOT EXISTS forked_from_chat_id UUID
    REFERENCES chats(id) ON DELETE SET NULL;

ALTER TABLE chats
  ADD COLUMN IF NOT EXISTS forked_from_project_id UUID
    REFERENCES projects(id) ON DELETE SET NULL;

-- ============================================================================
-- Helper: check whether a share is currently usable. Used by app code via
-- a SELECT, not as a constraint. Kept as a function so the rule is in one
-- place if we add more conditions later (rate limiting, IP allowlist, etc.).
-- ============================================================================

CREATE OR REPLACE FUNCTION is_share_active(share_row project_shares)
RETURNS BOOLEAN AS $$
BEGIN
  IF share_row.revoked_at IS NOT NULL THEN
    RETURN FALSE;
  END IF;
  IF share_row.expires_at IS NOT NULL AND share_row.expires_at <= now() THEN
    RETURN FALSE;
  END IF;
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION is_share_active IS 'Returns true if a project_shares row is still usable (not revoked, not expired).';
