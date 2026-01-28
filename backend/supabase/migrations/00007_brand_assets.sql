-- Migration: Brand Assets & Guidelines
-- Description: Create tables and storage for project brand assets and configuration
-- Created: 2026-01-28

-- ============================================================================
-- BRAND ASSETS TABLE
-- ============================================================================
-- Stores brand assets like logos, icons, fonts, and images
-- These are used by studio agents to maintain brand consistency in generated content

CREATE TABLE brand_assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  -- Asset metadata
  name TEXT NOT NULL,
  description TEXT,
  asset_type TEXT NOT NULL,

  -- File references (storage bucket path)
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  mime_type TEXT,
  file_size BIGINT,

  -- Additional metadata (dimensions, font metadata, etc.)
  metadata JSONB DEFAULT '{}'::jsonb,

  -- Primary flag for asset type (e.g., primary logo)
  is_primary BOOLEAN DEFAULT false,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Constraints
  CONSTRAINT valid_asset_type CHECK (asset_type IN ('logo', 'icon', 'font', 'image')),
  CONSTRAINT name_not_empty CHECK (length(trim(name)) > 0)
);

CREATE INDEX idx_brand_assets_project_id ON brand_assets(project_id);
CREATE INDEX idx_brand_assets_type ON brand_assets(asset_type);
CREATE INDEX idx_brand_assets_is_primary ON brand_assets(is_primary);

COMMENT ON TABLE brand_assets IS 'Brand assets (logos, icons, fonts, images) for studio content generation';
COMMENT ON COLUMN brand_assets.asset_type IS 'Type of asset: logo, icon, font, image';
COMMENT ON COLUMN brand_assets.file_path IS 'Storage bucket path to the asset file';
COMMENT ON COLUMN brand_assets.metadata IS 'Additional asset metadata (dimensions, font family, etc.)';
COMMENT ON COLUMN brand_assets.is_primary IS 'Whether this is the primary asset of its type';

-- ============================================================================
-- BRAND CONFIG TABLE
-- ============================================================================
-- Stores brand configuration (colors, typography, guidelines, voice)
-- One config per project, created on first access

CREATE TABLE brand_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  -- Color palette configuration
  colors JSONB DEFAULT '{
    "primary": "#000000",
    "secondary": "#666666",
    "accent": "#0066CC",
    "background": "#FFFFFF",
    "text": "#1A1A1A",
    "custom": []
  }'::jsonb,

  -- Typography settings
  typography JSONB DEFAULT '{
    "heading_font": "Inter",
    "body_font": "Inter",
    "heading_sizes": {"h1": "2.5rem", "h2": "2rem", "h3": "1.5rem"},
    "body_size": "1rem",
    "line_height": "1.6"
  }'::jsonb,

  -- Spacing configuration
  spacing JSONB DEFAULT '{
    "base": "1rem",
    "small": "0.5rem",
    "large": "2rem",
    "section": "4rem"
  }'::jsonb,

  -- Text guidelines (markdown supported)
  guidelines TEXT,

  -- Best practices (dos and don'ts)
  best_practices JSONB DEFAULT '{
    "dos": [],
    "donts": []
  }'::jsonb,

  -- Brand voice settings
  voice JSONB DEFAULT '{
    "tone": "professional",
    "personality": [],
    "keywords": []
  }'::jsonb,

  -- Per-feature settings (which studio features should apply brand)
  feature_settings JSONB DEFAULT '{
    "infographic": true,
    "presentation": true,
    "mind_map": false,
    "blog": true,
    "email": true,
    "ads_creative": true,
    "social_post": true,
    "prd": false,
    "business_report": true
  }'::jsonb,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE brand_config IS 'Brand configuration per project (colors, typography, guidelines, voice)';
COMMENT ON COLUMN brand_config.colors IS 'Color palette with primary, secondary, accent, background, text, and custom colors';
COMMENT ON COLUMN brand_config.typography IS 'Typography settings (fonts, sizes, line height)';
COMMENT ON COLUMN brand_config.spacing IS 'Spacing configuration (base, small, large, section)';
COMMENT ON COLUMN brand_config.guidelines IS 'Text brand guidelines (markdown supported)';
COMMENT ON COLUMN brand_config.best_practices IS 'Brand dos and donts arrays';
COMMENT ON COLUMN brand_config.voice IS 'Brand voice settings (tone, personality, keywords)';
COMMENT ON COLUMN brand_config.feature_settings IS 'Per-feature toggles for brand application';

-- ============================================================================
-- UPDATED_AT TRIGGERS
-- ============================================================================

CREATE TRIGGER update_brand_assets_updated_at BEFORE UPDATE ON brand_assets
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_brand_config_updated_at BEFORE UPDATE ON brand_config
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- STORAGE BUCKET FOR BRAND ASSETS
-- ============================================================================

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'brand-assets',
  'brand-assets',
  false, -- Not public, requires signed URLs
  52428800, -- 50MB limit
  ARRAY[
    'image/svg+xml',
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/x-icon',
    'font/ttf',
    'font/otf',
    'font/woff',
    'font/woff2',
    'application/pdf'
  ]
);

-- ============================================================================
-- STORAGE POLICIES FOR BRAND-ASSETS BUCKET
-- ============================================================================

-- Users can upload brand assets to their own projects
CREATE POLICY "Users can upload brand assets to own projects"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'brand-assets' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Users can read brand assets from their own projects
CREATE POLICY "Users can read brand assets from own projects"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'brand-assets' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Users can update brand assets in their own projects
CREATE POLICY "Users can update brand assets in own projects"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'brand-assets' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Users can delete brand assets from their own projects
CREATE POLICY "Users can delete brand assets from own projects"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'brand-assets' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- ============================================================================
-- HELPER FUNCTION FOR BRAND ASSET PATH
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_brand_asset_path(
  p_user_id UUID,
  p_project_id UUID,
  p_asset_id UUID,
  p_filename TEXT
)
RETURNS TEXT AS $$
BEGIN
  RETURN p_user_id || '/' || p_project_id || '/brand/' || p_asset_id || '/' || p_filename;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_brand_asset_path IS 'Generate storage path for brand assets: {user_id}/{project_id}/brand/{asset_id}/{filename}';

-- ============================================================================
-- RLS POLICIES FOR BRAND TABLES
-- ============================================================================

-- Enable RLS on brand tables
ALTER TABLE brand_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE brand_config ENABLE ROW LEVEL SECURITY;

-- Brand assets: Users can manage assets in their own projects
CREATE POLICY "Users can view own project brand assets"
ON brand_assets FOR SELECT
USING (
  project_id IN (
    SELECT id FROM projects WHERE user_id = auth.uid()
  )
);

CREATE POLICY "Users can insert brand assets to own projects"
ON brand_assets FOR INSERT
WITH CHECK (
  project_id IN (
    SELECT id FROM projects WHERE user_id = auth.uid()
  )
);

CREATE POLICY "Users can update own project brand assets"
ON brand_assets FOR UPDATE
USING (
  project_id IN (
    SELECT id FROM projects WHERE user_id = auth.uid()
  )
);

CREATE POLICY "Users can delete own project brand assets"
ON brand_assets FOR DELETE
USING (
  project_id IN (
    SELECT id FROM projects WHERE user_id = auth.uid()
  )
);

-- Brand config: Users can manage config in their own projects
CREATE POLICY "Users can view own project brand config"
ON brand_config FOR SELECT
USING (
  project_id IN (
    SELECT id FROM projects WHERE user_id = auth.uid()
  )
);

CREATE POLICY "Users can insert brand config to own projects"
ON brand_config FOR INSERT
WITH CHECK (
  project_id IN (
    SELECT id FROM projects WHERE user_id = auth.uid()
  )
);

CREATE POLICY "Users can update own project brand config"
ON brand_config FOR UPDATE
USING (
  project_id IN (
    SELECT id FROM projects WHERE user_id = auth.uid()
  )
);

CREATE POLICY "Users can delete own project brand config"
ON brand_config FOR DELETE
USING (
  project_id IN (
    SELECT id FROM projects WHERE user_id = auth.uid()
  )
);
