-- Migration: Add status_message column to studio_jobs.
-- Created: 2026-05-13
--
-- Studio job executors (presentation, blog, prd, website, video, ...) have
-- been writing a short live-status string via update_job(status_message=...),
-- and the API at /projects/{id}/active-tasks selects status_message to render
-- progress chips in the Studio panel. But the column was never created — the
-- writes were silently routed into job_data JSONB (status_message was not in
-- _TOP_COLUMNS) and the SELECT at active_tasks.py:77 has been failing with
-- 42703 "column studio_jobs.status_message does not exist" every 2-3 seconds
-- on every chat-open or studio-panel-open (which polls active-tasks).
--
-- Adding the column fixes the polling endpoint; the matching change in
-- studio_index_service._TOP_COLUMNS + create_job routes future writes to the
-- column instead of the JSONB. Old rows that still have a stale value buried
-- in job_data are harmless — the column reads NULL for them, which the
-- active_tasks _studio_job_detail() helper already handles via _GENERIC_*.

ALTER TABLE studio_jobs ADD COLUMN IF NOT EXISTS status_message TEXT;
