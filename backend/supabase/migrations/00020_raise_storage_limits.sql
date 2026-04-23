-- Migration: Raise storage bucket file size limits to 1GB
-- Description: Matches the new 1GB global upload limit in Flask (MAX_CONTENT_LENGTH)
--              and Supabase storage-api (FILE_SIZE_LIMIT).
--              Existing deployments had raw-files + processed-files at 100MB.
-- Created: 2026-04-23

UPDATE storage.buckets
SET file_size_limit = 1073741824  -- 1GB
WHERE id IN ('raw-files', 'processed-files');

-- Note: `chunks` stays at 10MB (text chunks are tiny, no need to grow).
-- `studio-outputs` stays at 500MB (AI-generated content, not user uploads).
