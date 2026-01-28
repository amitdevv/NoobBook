-- Migration: Google OAuth Tokens
-- Description: Add google_tokens column to users table for storing Google OAuth credentials
-- Created: 2026-01-28
--
-- Educational Note: Previously, Google OAuth tokens were stored in a single
-- data/google_tokens.json file, which meant all users shared the same Google
-- Drive connection. This migration moves tokens to the users table, enabling
-- per-user Google Drive connections for multi-user support.

-- ============================================================================
-- ADD GOOGLE TOKENS COLUMN TO USERS TABLE
-- ============================================================================

-- Add google_tokens JSONB column to store user-specific OAuth tokens
-- Note: App credentials (client_id, client_secret) are NOT stored here
-- They come from environment variables for security
-- Structure: {
--   "token": "access_token_here",
--   "refresh_token": "refresh_token_here",
--   "token_uri": "https://oauth2.googleapis.com/token",
--   "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
--   "google_email": "user@gmail.com",
--   "saved_at": "2026-01-28T12:00:00.000Z"
-- }
ALTER TABLE users
ADD COLUMN IF NOT EXISTS google_tokens JSONB DEFAULT NULL;

COMMENT ON COLUMN users.google_tokens IS 'Google OAuth tokens for Drive integration (per-user)';

-- ============================================================================
-- ADD INDEX FOR QUERYING CONNECTED USERS
-- ============================================================================

-- Index to efficiently find users with Google connected
-- Useful for admin dashboards showing connected accounts
CREATE INDEX IF NOT EXISTS idx_users_google_connected
ON users ((google_tokens IS NOT NULL));

-- ============================================================================
-- HELPER FUNCTION TO CHECK GOOGLE CONNECTION
-- ============================================================================

-- Function to check if a user has Google connected
CREATE OR REPLACE FUNCTION is_google_connected(p_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM users
    WHERE id = p_user_id
    AND google_tokens IS NOT NULL
    AND google_tokens->>'refresh_token' IS NOT NULL
  );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION is_google_connected IS 'Check if a user has valid Google OAuth tokens stored';
