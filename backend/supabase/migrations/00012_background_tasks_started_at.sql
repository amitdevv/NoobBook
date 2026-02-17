-- Add started_at column to background_tasks for tracking when a task begins processing
ALTER TABLE background_tasks ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
