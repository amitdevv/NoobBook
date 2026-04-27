-- Migration: Project forks (Roadmap #15 follow-up).
-- Created: 2026-04-28
--
-- Replaces the chat-only "Shared with me" fork from migration 00021 with
-- full project cloning. When a viewer of a shared project clicks
-- "Make a copy in your workspace", we now duplicate the entire project
-- (sources + chunks + chats + messages + Pinecone vectors) into a brand-
-- new project owned by the viewer, with provenance recorded here.

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS forked_from_project_id UUID
    REFERENCES projects(id) ON DELETE SET NULL;

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS forked_from_user_id UUID
    REFERENCES users(id) ON DELETE SET NULL;

-- Index for the breadcrumb / "all forks of project X" admin query path.
CREATE INDEX IF NOT EXISTS projects_forked_from_project_id_idx
  ON projects (forked_from_project_id)
  WHERE forked_from_project_id IS NOT NULL;

-- The "Shared with me" auto-project is going away: each fork now becomes
-- its own first-class project. Drop the partial unique index added in
-- 00021 so multiple forks per user are allowed (and so a user can choose
-- to literally name a project "Shared with me" if they want).
DROP INDEX IF EXISTS projects_shared_with_me_per_user_uniq;
