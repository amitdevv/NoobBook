-- Studio Jobs table — replaces studio_index.json
-- Stores all studio content generation job metadata in Supabase
-- instead of local JSON files.

CREATE TABLE IF NOT EXISTS studio_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,          -- 'audio', 'video', 'presentation', etc.
    source_id UUID,                  -- Optional reference to source
    source_name TEXT,
    direction TEXT,                   -- User's generation instructions
    status TEXT NOT NULL DEFAULT 'pending',
    progress TEXT,
    error_message TEXT,
    job_data JSONB DEFAULT '{}'::jsonb,  -- Type-specific fields (audio_path, videos[], slides[], etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_studio_jobs_project_id ON studio_jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_studio_jobs_project_type ON studio_jobs(project_id, job_type);
CREATE INDEX IF NOT EXISTS idx_studio_jobs_status ON studio_jobs(status);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_studio_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_studio_jobs_updated_at
    BEFORE UPDATE ON studio_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_studio_jobs_updated_at();
