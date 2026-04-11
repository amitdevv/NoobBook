-- Add cost tracking column to chats table.
--
-- Mirrors the `projects.costs` JSONB structure so we can use the same
-- cost_tracking utility to update both in one locked operation.
--
-- Existing chats get the default on first cost write via
-- _ensure_cost_structure() in app/utils/cost_tracking.py.

ALTER TABLE chats
  ADD COLUMN IF NOT EXISTS costs JSONB DEFAULT '{
    "total_cost": 0,
    "by_model": {
      "opus": {"input_tokens": 0, "output_tokens": 0, "cost": 0},
      "sonnet": {"input_tokens": 0, "output_tokens": 0, "cost": 0},
      "haiku": {"input_tokens": 0, "output_tokens": 0, "cost": 0}
    }
  }'::jsonb;

COMMENT ON COLUMN chats.costs IS 'Per-chat cost tracking: total_cost + by_model breakdown (opus/sonnet/haiku)';
