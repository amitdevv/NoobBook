-- Migration: Chat Attachments RLS — mirror raw-files policy shape
-- Description: 00028 replaced the four 00027 policies with a single
--              permissive policy scoped `TO service_role`. That looked
--              correct on paper but storage uploads kept failing on the
--              customer's self-hosted deploy with:
--                "new row violates row-level security policy"
--              even after 00028 had been applied. raw-files uploads
--              against the same Supabase instance work fine using the
--              original 00002 four-policy shape (no TO clause, with the
--              `auth.uid() = first_folder` check that can never match
--              for service-role uploads). That means storage-api here
--              isn't actually evaluating as the `service_role` Postgres
--              role — it's connecting as a role that bypasses RLS only
--              when no role-restricted policy intercepts it. Restricting
--              to `TO service_role` accidentally narrowed the policy
--              away from the role doing the insert, so the bucket fell
--              back to RLS-deny.
--
--              Fix: drop the 00028 single policy and recreate the same
--              four-policy shape as raw-files. The check
--              `auth.uid() = first_folder` is intentionally a no-op for
--              the backend path (first folder is project_id, not user
--              id) — what matters is the policies exist without a `TO`
--              filter so the storage-api connection role can satisfy
--              them via its own bypass.
-- Created: 2026-05-12

-- Drop the single permissive policy introduced in 00028.
DROP POLICY IF EXISTS "Chat attachments — backend-mediated full access" ON storage.objects;

-- Also drop the four 00027 names in case any deploy still has them
-- around (idempotent on already-clean targets).
DROP POLICY IF EXISTS "Users can upload chat attachments to own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can read chat attachments from own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can update chat attachments in own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can delete chat attachments from own projects" ON storage.objects;

-- Recreate raw-files-style policies. No TO clause = TO public, mirrors
-- how raw-files / processed-files / chunks / studio-outputs are scoped
-- in 00002 and brand-assets in 00007. PG 15 doesn't accept
-- `CREATE POLICY IF NOT EXISTS`, so the DROPs above clear the slate
-- for safe re-application.
CREATE POLICY "Users can upload chat attachments to own projects"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'chat-attachments' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can read chat attachments from own projects"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'chat-attachments' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can update chat attachments in own projects"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'chat-attachments' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can delete chat attachments from own projects"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'chat-attachments' AND
  auth.uid()::text = (storage.foldername(name))[1]
);
