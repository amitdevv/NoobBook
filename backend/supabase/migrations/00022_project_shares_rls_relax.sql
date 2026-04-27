-- Migration: Relax RLS on project_shares so the Flask backend can write.
-- Created: 2026-04-28
--
-- Why this exists
-- ---------------
-- 00021 added INSERT/UPDATE/SELECT policies on project_shares keyed on
-- ``auth.uid() = projects.user_id`` (defense-in-depth on Greptile's P1
-- review). That assumed the Flask backend either:
--   a) connects with the Supabase service-role key, which bypasses RLS, OR
--   b) forwards the user's JWT so auth.uid() resolves correctly.
--
-- In practice the backend uses a singleton Supabase client (see
-- ``supabase_client.py``) that does NOT forward the user JWT, and on
-- self-hosted deployments the service-role bypass isn't always wired up.
-- Result: legitimate share creation fails with
--   "new row violates row-level security policy for table project_shares"
-- even though the route handler has already validated project ownership.
--
-- This migration drops the policies and disables RLS on the table. The
-- Flask layer continues to enforce ownership in ``app/api/projects/shares.py``
-- (every endpoint calls ``project_service.get_project(..., user_id=...)``
-- and 404s non-owners). This matches how every other table in the codebase
-- behaves in practice — RLS is enabled but service-role bypasses it.

DROP POLICY IF EXISTS "Owners can read their project shares" ON project_shares;
DROP POLICY IF EXISTS "Owners can create their project shares" ON project_shares;
DROP POLICY IF EXISTS "Owners can update their project shares" ON project_shares;

ALTER TABLE project_shares DISABLE ROW LEVEL SECURITY;
