-- Migration: Move Brand Kit from Project-Level to User-Level
-- Description: Brand config and assets become workspace-level (per-user) settings
-- instead of per-project. This lets users share brand identity across all projects.
-- Created: 2026-02-07

-- ============================================================================
-- STEP 1: Add user_id column to both tables (nullable initially)
-- ============================================================================

ALTER TABLE brand_config ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE brand_assets ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- ============================================================================
-- STEP 2: Backfill user_id from projects table
-- ============================================================================

UPDATE brand_config bc
SET user_id = p.user_id
FROM projects p
WHERE bc.project_id = p.id;

UPDATE brand_assets ba
SET user_id = p.user_id
FROM projects p
WHERE ba.project_id = p.id;

-- ============================================================================
-- STEP 3: Deduplicate brand_config (keep most recently updated per user)
-- ============================================================================
-- A user may have configured brand differently across multiple projects.
-- Keep only the most recently updated config per user.

DELETE FROM brand_config
WHERE id NOT IN (
  SELECT DISTINCT ON (user_id) id
  FROM brand_config
  WHERE user_id IS NOT NULL
  ORDER BY user_id, updated_at DESC
);

-- brand_assets: keep all assets (no dedup needed, they're all useful)

-- ============================================================================
-- STEP 4: Make user_id NOT NULL
-- ============================================================================

ALTER TABLE brand_config ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE brand_assets ALTER COLUMN user_id SET NOT NULL;

-- ============================================================================
-- STEP 5: Drop project_id columns and old constraints/indexes
-- ============================================================================

-- Drop old indexes
DROP INDEX IF EXISTS idx_brand_assets_project_id;

-- Drop project_id from brand_config (has UNIQUE constraint)
ALTER TABLE brand_config DROP CONSTRAINT IF EXISTS brand_config_project_id_key;
ALTER TABLE brand_config DROP CONSTRAINT IF EXISTS brand_config_project_id_fkey;
ALTER TABLE brand_config DROP COLUMN project_id;

-- Drop project_id from brand_assets
ALTER TABLE brand_assets DROP CONSTRAINT IF EXISTS brand_assets_project_id_fkey;
ALTER TABLE brand_assets DROP COLUMN project_id;

-- ============================================================================
-- STEP 6: Add new constraints and indexes
-- ============================================================================

-- One brand config per user
ALTER TABLE brand_config ADD CONSTRAINT brand_config_user_id_key UNIQUE (user_id);

-- Fast lookup by user
CREATE INDEX idx_brand_assets_user_id ON brand_assets(user_id);
CREATE INDEX idx_brand_config_user_id ON brand_config(user_id);

-- ============================================================================
-- STEP 7: Drop and recreate RLS policies (user_id = auth.uid() directly)
-- ============================================================================

-- Drop old brand_assets policies
DROP POLICY IF EXISTS "Users can view own project brand assets" ON brand_assets;
DROP POLICY IF EXISTS "Users can insert brand assets to own projects" ON brand_assets;
DROP POLICY IF EXISTS "Users can update own project brand assets" ON brand_assets;
DROP POLICY IF EXISTS "Users can delete own project brand assets" ON brand_assets;

-- Drop old brand_config policies
DROP POLICY IF EXISTS "Users can view own project brand config" ON brand_config;
DROP POLICY IF EXISTS "Users can insert brand config to own projects" ON brand_config;
DROP POLICY IF EXISTS "Users can update own project brand config" ON brand_config;
DROP POLICY IF EXISTS "Users can delete own project brand config" ON brand_config;

-- New brand_assets policies (direct user_id match — faster than subquery)
CREATE POLICY "Users can view own brand assets"
ON brand_assets FOR SELECT
USING (user_id = auth.uid());

CREATE POLICY "Users can insert own brand assets"
ON brand_assets FOR INSERT
WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own brand assets"
ON brand_assets FOR UPDATE
USING (user_id = auth.uid());

CREATE POLICY "Users can delete own brand assets"
ON brand_assets FOR DELETE
USING (user_id = auth.uid());

-- New brand_config policies
CREATE POLICY "Users can view own brand config"
ON brand_config FOR SELECT
USING (user_id = auth.uid());

CREATE POLICY "Users can insert own brand config"
ON brand_config FOR INSERT
WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own brand config"
ON brand_config FOR UPDATE
USING (user_id = auth.uid());

CREATE POLICY "Users can delete own brand config"
ON brand_config FOR DELETE
USING (user_id = auth.uid());

-- ============================================================================
-- STEP 8: Update helper function (remove project_id from path)
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_brand_asset_path(
  p_user_id UUID,
  p_asset_id UUID,
  p_filename TEXT
)
RETURNS TEXT AS $$
BEGIN
  RETURN p_user_id || '/brand/' || p_asset_id || '/' || p_filename;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_brand_asset_path(UUID, UUID, TEXT)
IS 'Generate storage path for brand assets: {user_id}/brand/{asset_id}/{filename}';

-- Drop old 4-parameter version if it exists
DROP FUNCTION IF EXISTS generate_brand_asset_path(UUID, UUID, UUID, TEXT);

-- ============================================================================
-- STEP 9: Update table comments
-- ============================================================================

COMMENT ON TABLE brand_config IS 'Brand configuration per user (colors, typography, guidelines, voice) — workspace-level setting';
COMMENT ON TABLE brand_assets IS 'Brand assets (logos, icons, fonts, images) per user — workspace-level setting';
