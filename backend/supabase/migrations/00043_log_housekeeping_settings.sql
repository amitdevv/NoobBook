-- Global app-settings row for the log housekeeping scheduler.
--
-- Single-row table guarded by a CHECK on a boolean PK so we never end up
-- with multiple rows competing for "the global config." The scheduler
-- reads this every tick; the admin toggle in Settings → Logs writes to it.

CREATE TABLE IF NOT EXISTS app_settings (
  id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id = TRUE),
  log_housekeeping JSONB NOT NULL
    DEFAULT '{"weekly_clear_enabled": true, "last_run_at": null}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO app_settings (id) VALUES (TRUE) ON CONFLICT DO NOTHING;

COMMENT ON TABLE app_settings IS
  'Single-row global app settings. Currently holds log housekeeping flags '
  '(weekly_clear_enabled, last_run_at). Add new JSONB columns here for '
  'future global toggles.';
