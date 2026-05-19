-- Persistent storage for API keys saved via Admin Settings → API Keys.
--
-- Before this migration, env_service.set_key() wrote to /app/.env inside the
-- container. That file is excluded by backend/.dockerignore and lives on the
-- container's ephemeral filesystem (only /app/data is volumed), so every key
-- saved through the UI evaporated on the next container restart.
--
-- We now route writes through app_settings.api_keys instead. Values are
-- Fernet-encrypted in the application layer before insert; the decryption
-- key is derived from the SECRET_KEY env var. The column is JSONB so each
-- API_KEY_NAME maps to one ciphertext entry.

ALTER TABLE app_settings
  ADD COLUMN IF NOT EXISTS api_keys JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN app_settings.api_keys IS
  'Map of API_KEY_NAME -> Fernet-encrypted ciphertext (base64). Decryption '
  'key is derived from the SECRET_KEY env var via SHA-256 → urlsafe-base64. '
  'Rotating SECRET_KEY invalidates stored ciphertexts — admins must re-save. '
  'Service-role only via Supabase default RLS (no permissive policies grant '
  'anon/authenticated access to this table).';
