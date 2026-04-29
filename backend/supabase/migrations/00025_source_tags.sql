-- 00025_source_tags.sql
-- Adds a free-form tags array to sources. Lets users group / filter
-- their sources without imposing a folder hierarchy.
-- Lowercased on write, deduplicated, deletion-safe.

ALTER TABLE sources
  ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';

-- GIN index lets us filter "sources where tags @> ARRAY['python']"
-- in O(log n). Same pattern Postgres docs recommend for tag tables.
CREATE INDEX IF NOT EXISTS idx_sources_tags ON sources USING GIN (tags);
