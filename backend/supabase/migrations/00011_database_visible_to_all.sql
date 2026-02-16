-- Add visible_to_all flag to database_connections
-- When true, all users (not just admins/owners) can see and use the connection.
ALTER TABLE database_connections
  ADD COLUMN IF NOT EXISTS visible_to_all BOOLEAN NOT NULL DEFAULT true;
