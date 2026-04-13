-- Per-user module permissions.
--
-- NULL = all permissions enabled (default for all existing users).
-- Only stores a JSONB object when an admin explicitly customizes
-- a user's access via Settings → Team → Edit Permissions.
--
-- Structure:
-- {
--   "document_sources": { "enabled": true, "items": { "pdf": true, ... } },
--   "data_sources":     { "enabled": true, "items": { "database": true, ... } },
--   "studio":           { "enabled": true, "items": { "flow_diagrams": true, ... } },
--   "integrations":     { "enabled": true, "items": { "jira": true, ... } },
--   "chat_features":    { "enabled": true, "items": { "memory": true, ... } }
-- }

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS permissions JSONB DEFAULT NULL;

COMMENT ON COLUMN users.permissions IS 'Per-user module permissions. NULL = all enabled (default).';
