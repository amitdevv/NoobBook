-- 00026_source_versions.sql
-- Append-only history for in-place edits of TEXT sources. Each call
-- to text_upload.update_text snapshots the previous markdown body
-- here before overwriting the raw file. Lets the editor offer a
-- "view / restore previous version" affordance.
--
-- We don't store version data for non-TEXT sources — those can't be
-- edited in place (delete + re-upload) so versioning is meaningless.

CREATE TABLE IF NOT EXISTS source_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  -- Markdown body at the time the snapshot was taken. We store the
  -- full doc rather than a diff because TEXT sources are typically
  -- < 100KB and cleanly diffing markdown is non-trivial.
  content TEXT NOT NULL,
  -- Display name at the time of snapshot (rename history).
  name TEXT NOT NULL,
  -- Author would be nice eventually; for now we only know "the
  -- editor saved this." Adding a column avoids a migration later.
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_versions_source_id_created_at
  ON source_versions (source_id, created_at DESC);

-- RLS: a user can read versions of any source in a project they have
-- access to (mirrors the sources table policy).
ALTER TABLE source_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS source_versions_read ON source_versions;
CREATE POLICY source_versions_read ON source_versions
  FOR SELECT USING (
    EXISTS (
      SELECT 1
      FROM sources s
      JOIN projects p ON p.id = s.project_id
      WHERE s.id = source_versions.source_id
        AND p.user_id = auth.uid()
    )
  );

-- Service role bypasses RLS; the backend writes via that role so we
-- don't need an INSERT policy.
