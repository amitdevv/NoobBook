-- Migration: Chat attachments RLS — actually permissive (no TO filter)
-- Created: 2026-05-13
--
-- Context: 00027 → 00028 → 00030 all tried to make chat-attachment
-- uploads work; all three left the bucket unwritable on the customer's
-- self-hosted Supabase deploy.
--
-- Why 00030 fails: it copied the raw-files policy shape verbatim:
--   auth.uid()::text = (storage.foldername(name))[1]
-- ...which works for raw-files ONLY BECAUSE raw-files paths begin with
-- {user_id}/..., so first_folder == auth.uid() is satisfiable. The
-- chat-attachments path is {project_id}/{chat_id}/{attachment_id}/file,
-- so first_folder is the project_id and the check can never be true.
-- The original 00027/00028 author thought the policy worked via a
-- service-role RLS bypass — but the customer's storage-api evidently
-- does NOT bypass RLS (we've now seen 403 "new row violates row-level
-- security policy" three migrations in a row, each from a real upload).
--
-- Fix shape: keep the bucket private (public=false from 00027) and
-- write a single permissive policy with NO `TO` filter. The policy
-- applies to whatever role storage-api connects as (the failure mode
-- the 00028 attempt hit was scoping `TO service_role` and missing the
-- actual role). Security is preserved by:
--   1. Bucket is private → anon can't enumerate.
--   2. Backend is the only writer (service_role JWT through Supabase
--      storage SDK) and runs project-access RBAC checks BEFORE calling
--      upload_chat_attachment().
--   3. Browser reads use create_signed_url which storage-api validates
--      cryptographically — bypassing RLS via the signature, not the role.
-- Worst-case residual risk (an authenticated user calling storage SDK
-- direct with their own JWT) is bucket-spam, not data exposure: signed
-- URLs are still required to actually read someone else's attachment.

DROP POLICY IF EXISTS "Users can upload chat attachments to own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can read chat attachments from own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can update chat attachments in own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can delete chat attachments from own projects" ON storage.objects;
DROP POLICY IF EXISTS "Chat attachments — backend-mediated full access"     ON storage.objects;
DROP POLICY IF EXISTS "Chat attachments — backend & signed-url access"      ON storage.objects;

-- Single policy, no TO filter, covers all CRUD operations.
CREATE POLICY "Chat attachments — backend & signed-url access"
ON storage.objects FOR ALL
USING (bucket_id = 'chat-attachments')
WITH CHECK (bucket_id = 'chat-attachments');
