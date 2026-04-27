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
-- UNIQUE gives a btree, but a partial index over non-revoked rows keeps
-- the lookup fast even after many revocations accumulate.
-- Note: this index intentionally does NOT filter on `expires_at` because
-- `now()` is not IMMUTABLE and Postgres rejects it inside index predicates.
-- Expiry is checked at query time via is_share_active() / Python.
CREATE INDEX IF NOT EXISTS project_shares_non_revoked_token_idx
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
-- STABLE (not IMMUTABLE): the function calls now(), so its value is
-- consistent within a single statement / transaction but NOT across
-- transactions. IMMUTABLE would let Postgres cache stale "active"
-- evaluations indefinitely.
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION is_share_active IS 'Returns true if a project_shares row is still usable (not revoked, not expired).';

-- ============================================================================
-- Row-Level Security
-- The Flask backend uses the service-role key (bypasses RLS), so policies
-- here are a defense-in-depth lock against any anon-key client (or a
-- credential leak) reading or mutating share rows directly. End users
-- never touch this table from the frontend — they go through Flask, which
-- enforces ownership in app code.
-- ============================================================================

ALTER TABLE project_shares ENABLE ROW LEVEL SECURITY;

-- Owners can read share rows for projects they own.
CREATE POLICY "Owners can read their project shares"
ON project_shares FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM projects p
    WHERE p.id = project_shares.project_id
      AND p.user_id = auth.uid()
  )
);

-- Owners can create share rows for projects they own.
CREATE POLICY "Owners can create their project shares"
ON project_shares FOR INSERT
WITH CHECK (
  created_by = auth.uid()
  AND EXISTS (
    SELECT 1 FROM projects p
    WHERE p.id = project_shares.project_id
      AND p.user_id = auth.uid()
  )
);

-- Owners can update (revoke) share rows for projects they own.
CREATE POLICY "Owners can update their project shares"
ON project_shares FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM projects p
    WHERE p.id = project_shares.project_id
      AND p.user_id = auth.uid()
  )
);

-- DELETE intentionally not granted: shares are revoked by setting
-- revoked_at, never hard-deleted, so the audit trail stays intact.

-- ============================================================================
-- "Shared with me" idempotency guard.
-- The fork flow auto-creates a project named "Shared with me" per user.
-- Without a unique constraint, two concurrent forks from the same viewer
-- can each pass the check-then-insert race and end up creating duplicate
-- projects. A partial unique index makes the second insert raise a
-- constraint violation that ensure_shared_with_me_project() can recover
-- from by re-fetching.
-- ============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS projects_shared_with_me_per_user_uniq
  ON projects (user_id)
  WHERE name = 'Shared with me';
