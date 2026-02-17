-- NoobBook Database Initialization
-- Run this SQL in Supabase SQL Editor for fresh setup
-- Combines all migrations into a single file

-- ============================================================================
-- EXTENSIONS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE,
  role TEXT NOT NULL DEFAULT 'user',
  memory JSONB DEFAULT '{}'::jsonb,
  settings JSONB DEFAULT '{}'::jsonb,
  google_tokens JSONB DEFAULT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT valid_user_role CHECK (role IN ('admin', 'user'))
);

-- Backfill/migrate role column for existing installations
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

-- Default user for single-user mode
INSERT INTO users (id, email, role, memory, settings)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'local@noobbook.local',
  'admin',
  '{}'::jsonb,
  '{}'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- Ensure the default user is admin (for single-user mode)
UPDATE users
SET role = 'admin'
WHERE id = '00000000-0000-0000-0000-000000000001'
  AND role <> 'admin';

-- ============================================================================
-- PROJECTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE DEFAULT '00000000-0000-0000-0000-000000000001',
  name TEXT NOT NULL,
  description TEXT,
  custom_prompt TEXT,
  memory JSONB DEFAULT '{}'::jsonb,
  costs JSONB DEFAULT '{
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0,
    "by_model": {}
  }'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_accessed TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_last_accessed ON projects(last_accessed DESC);

-- ============================================================================
-- SOURCES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded',
  raw_file_path TEXT,
  processed_file_path TEXT,
  token_count INTEGER,
  page_count INTEGER,
  file_size BIGINT,
  embedding_info JSONB DEFAULT '{}'::jsonb,
  summary_info JSONB DEFAULT '{}'::jsonb,
  processing_info JSONB DEFAULT '{}'::jsonb,
  error_message TEXT,
  url TEXT,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sources_project_id ON sources(project_id);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(type);

-- ============================================================================
-- DATABASE CONNECTIONS (Account-level)
-- ============================================================================
CREATE TABLE IF NOT EXISTS database_connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  db_type TEXT NOT NULL,
  connection_uri TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  visible_to_all BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT valid_db_type CHECK (db_type IN ('postgresql', 'mysql')),
  CONSTRAINT name_not_empty CHECK (length(trim(name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_database_connections_owner_user_id ON database_connections(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_database_connections_db_type ON database_connections(db_type);

-- Users allowed to use a database connection (for multi-user mode)
CREATE TABLE IF NOT EXISTS database_connection_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id UUID NOT NULL REFERENCES database_connections(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(connection_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_database_connection_users_connection_id ON database_connection_users(connection_id);
CREATE INDEX IF NOT EXISTS idx_database_connection_users_user_id ON database_connection_users(user_id);

-- ============================================================================
-- CHATS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS chats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'New Chat',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chats_project_id ON chats(project_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at DESC);

-- ============================================================================
-- MESSAGES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content JSONB NOT NULL,
  citations TEXT[] DEFAULT ARRAY[]::TEXT[],
  model TEXT,
  tokens_input INTEGER,
  tokens_output INTEGER,
  cost_usd NUMERIC(10, 6),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- ============================================================================
-- CHUNKS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  page_number INTEGER,
  chunk_number INTEGER,
  token_count INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);

-- ============================================================================
-- BACKGROUND TASKS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS background_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_id UUID NOT NULL,
  target_type TEXT NOT NULL,
  task_type TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  progress INTEGER DEFAULT 0,
  message TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tasks_target ON background_tasks(target_id, target_type);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON background_tasks(status);

-- ============================================================================
-- STUDIO SIGNALS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS studio_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
  studio_item TEXT NOT NULL,
  direction TEXT NOT NULL,
  source_ids UUID[] DEFAULT ARRAY[]::UUID[],
  status TEXT DEFAULT 'pending',
  output_path TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_studio_signals_chat_id ON studio_signals(chat_id);

-- ============================================================================
-- BRAND ASSETS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS brand_assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  asset_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  mime_type TEXT,
  file_size BIGINT,
  metadata JSONB DEFAULT '{}'::jsonb,
  is_primary BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT valid_asset_type CHECK (asset_type IN ('logo', 'icon', 'font', 'image')),
  CONSTRAINT name_not_empty CHECK (length(trim(name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_brand_assets_user_id ON brand_assets(user_id);
CREATE INDEX IF NOT EXISTS idx_brand_assets_type ON brand_assets(asset_type);

-- ============================================================================
-- BRAND CONFIG TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS brand_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  colors JSONB DEFAULT '{
    "primary": "#000000",
    "secondary": "#666666",
    "accent": "#0066CC",
    "background": "#FFFFFF",
    "text": "#1A1A1A",
    "custom": []
  }'::jsonb,
  typography JSONB DEFAULT '{
    "heading_font": "Inter",
    "body_font": "Inter",
    "heading_sizes": {"h1": "2.5rem", "h2": "2rem", "h3": "1.5rem"},
    "body_size": "1rem",
    "line_height": "1.6"
  }'::jsonb,
  spacing JSONB DEFAULT '{
    "base": "1rem",
    "small": "0.5rem",
    "large": "2rem",
    "section": "4rem"
  }'::jsonb,
  guidelines TEXT,
  best_practices JSONB DEFAULT '{"dos": [], "donts": []}'::jsonb,
  voice JSONB DEFAULT '{"tone": "professional", "personality": [], "keywords": []}'::jsonb,
  feature_settings JSONB DEFAULT '{
    "chat": true,
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
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sources_updated_at ON sources;
CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_database_connections_updated_at ON database_connections;
CREATE TRIGGER update_database_connections_updated_at BEFORE UPDATE ON database_connections
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chats_updated_at ON chats;
CREATE TRIGGER update_chats_updated_at BEFORE UPDATE ON chats
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_background_tasks_updated_at ON background_tasks;
CREATE TRIGGER update_background_tasks_updated_at BEFORE UPDATE ON background_tasks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_studio_signals_updated_at ON studio_signals;
CREATE TRIGGER update_studio_signals_updated_at BEFORE UPDATE ON studio_signals
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_brand_assets_updated_at ON brand_assets;
CREATE TRIGGER update_brand_assets_updated_at BEFORE UPDATE ON brand_assets
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_brand_config_updated_at ON brand_config;
CREATE TRIGGER update_brand_config_updated_at BEFORE UPDATE ON brand_config
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================
CREATE OR REPLACE FUNCTION update_project_last_accessed(p_project_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE projects SET last_accessed = NOW() WHERE id = p_project_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_project_stats(p_project_id UUID)
RETURNS JSON AS $$
DECLARE
  v_stats JSON;
BEGIN
  SELECT json_build_object(
    'total_sources', (SELECT COUNT(*) FROM sources WHERE project_id = p_project_id),
    'active_sources', (SELECT COUNT(*) FROM sources WHERE project_id = p_project_id AND is_active = true),
    'total_chats', (SELECT COUNT(*) FROM chats WHERE project_id = p_project_id),
    'total_messages', (
      SELECT COUNT(*) FROM messages m
      JOIN chats c ON c.id = m.chat_id
      WHERE c.project_id = p_project_id
    )
  ) INTO v_stats;
  RETURN v_stats;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION is_google_connected(p_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM users
    WHERE id = p_user_id
    AND google_tokens IS NOT NULL
    AND google_tokens->>'refresh_token' IS NOT NULL
  );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STORAGE BUCKETS
-- ============================================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('raw-files', 'raw-files', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public)
VALUES ('processed-files', 'processed-files', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public)
VALUES ('chunks', 'chunks', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public)
VALUES ('studio-outputs', 'studio-outputs', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'brand-assets',
  'brand-assets',
  false,
  52428800,
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
) ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STORAGE POLICIES (Single-user mode - allow all)
-- ============================================================================
DO $$
BEGIN
  -- Raw files
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on raw-files') THEN
    CREATE POLICY "Allow all on raw-files" ON storage.objects FOR ALL
    USING (bucket_id = 'raw-files') WITH CHECK (bucket_id = 'raw-files');
  END IF;

  -- Processed files
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on processed-files') THEN
    CREATE POLICY "Allow all on processed-files" ON storage.objects FOR ALL
    USING (bucket_id = 'processed-files') WITH CHECK (bucket_id = 'processed-files');
  END IF;

  -- Chunks
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on chunks') THEN
    CREATE POLICY "Allow all on chunks" ON storage.objects FOR ALL
    USING (bucket_id = 'chunks') WITH CHECK (bucket_id = 'chunks');
  END IF;

  -- Studio outputs
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on studio-outputs') THEN
    CREATE POLICY "Allow all on studio-outputs" ON storage.objects FOR ALL
    USING (bucket_id = 'studio-outputs') WITH CHECK (bucket_id = 'studio-outputs');
  END IF;

  -- Brand assets
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on brand-assets') THEN
    CREATE POLICY "Allow all on brand-assets" ON storage.objects FOR ALL
    USING (bucket_id = 'brand-assets') WITH CHECK (bucket_id = 'brand-assets');
  END IF;
END $$;

-- ============================================================================
-- STUDIO JOBS TABLE (replaces studio_index.json)
-- ============================================================================
CREATE TABLE IF NOT EXISTS studio_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    source_id UUID,
    source_name TEXT,
    direction TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    progress TEXT,
    error_message TEXT,
    job_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_studio_jobs_project_id ON studio_jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_studio_jobs_project_type ON studio_jobs(project_id, job_type);
CREATE INDEX IF NOT EXISTS idx_studio_jobs_status ON studio_jobs(status);

CREATE OR REPLACE FUNCTION update_studio_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_studio_jobs_updated_at ON studio_jobs;
CREATE TRIGGER trigger_studio_jobs_updated_at
    BEFORE UPDATE ON studio_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_studio_jobs_updated_at();
