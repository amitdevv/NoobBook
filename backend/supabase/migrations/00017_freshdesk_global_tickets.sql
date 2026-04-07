-- ============================================================================
-- FRESHDESK TICKETS: GLOBAL DATA STORE
-- Ensures the freshdesk_tickets table exists (creates if missing, e.g. when
-- migration 00016 was seeded but never ran), then migrates from per-source
-- to global ticket storage keyed by ticket_id alone.
-- ============================================================================

-- Step 0: Create the table if it doesn't exist yet (idempotent with 00016)
CREATE TABLE IF NOT EXISTS freshdesk_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID,
  project_id UUID,
  ticket_id BIGINT NOT NULL,
  subject TEXT,
  description_text TEXT,
  status TEXT,
  priority TEXT,
  ticket_type TEXT,
  source_channel TEXT,
  requester_name TEXT,
  requester_email TEXT,
  requester_id BIGINT,
  agent_name TEXT,
  agent_email TEXT,
  responder_id BIGINT,
  group_name TEXT,
  group_id BIGINT,
  product_name TEXT,
  product_id BIGINT,
  company_name TEXT,
  company_id BIGINT,
  category TEXT,
  subcategory TEXT,
  tags TEXT[] DEFAULT '{}',
  ticket_created_at TIMESTAMPTZ,
  ticket_updated_at TIMESTAMPTZ,
  due_by TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  first_responded_at TIMESTAMPTZ,
  resolution_time_hours NUMERIC(10, 2),
  first_response_time_hours NUMERIC(10, 2),
  is_escalated BOOLEAN DEFAULT false,
  custom_fields JSONB DEFAULT '{}'::jsonb,
  synced_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 1: Drop old per-source constraints and foreign keys
ALTER TABLE freshdesk_tickets DROP CONSTRAINT IF EXISTS freshdesk_tickets_source_ticket_unique;
ALTER TABLE freshdesk_tickets DROP CONSTRAINT IF EXISTS freshdesk_tickets_source_id_fkey;
ALTER TABLE freshdesk_tickets DROP CONSTRAINT IF EXISTS freshdesk_tickets_project_id_fkey;

-- Step 2: Make source_id and project_id nullable (may already be from CREATE above)
DO $$ BEGIN
  ALTER TABLE freshdesk_tickets ALTER COLUMN source_id DROP NOT NULL;
EXCEPTION WHEN others THEN NULL;
END $$;
DO $$ BEGIN
  ALTER TABLE freshdesk_tickets ALTER COLUMN project_id DROP NOT NULL;
EXCEPTION WHEN others THEN NULL;
END $$;

-- Step 3: Deduplicate existing rows BEFORE adding the unique constraint.
-- The original schema allowed the same ticket_id to exist for different
-- sources. Going global means we must keep only one row per ticket_id —
-- we keep the most recently synced row.
DELETE FROM freshdesk_tickets
WHERE id IN (
  SELECT id FROM (
    SELECT id,
           ROW_NUMBER() OVER (
             PARTITION BY ticket_id
             ORDER BY synced_at DESC NULLS LAST, created_at DESC NULLS LAST
           ) AS rn
    FROM freshdesk_tickets
  ) ranked
  WHERE ranked.rn > 1
);

-- Step 4: Add global unique constraint on ticket_id alone (skip if exists).
-- We check pg_constraint explicitly because adding an existing UNIQUE
-- constraint can fail with either `duplicate_object` (42710) for the
-- constraint or `duplicate_table` (42P07) for the underlying index name.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'freshdesk_tickets_ticket_unique'
      AND conrelid = 'freshdesk_tickets'::regclass
  ) THEN
    ALTER TABLE freshdesk_tickets
      ADD CONSTRAINT freshdesk_tickets_ticket_unique UNIQUE (ticket_id);
  END IF;
END $$;

-- Step 5: Drop old source-scoped indexes
DROP INDEX IF EXISTS idx_freshdesk_tickets_source_id;
DROP INDEX IF EXISTS idx_freshdesk_tickets_status;
DROP INDEX IF EXISTS idx_freshdesk_tickets_created;
DROP INDEX IF EXISTS idx_freshdesk_tickets_agent;

-- Step 6: Create new global indexes
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_status_global ON freshdesk_tickets(status);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_created_global ON freshdesk_tickets(ticket_created_at DESC);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_agent_global ON freshdesk_tickets(agent_name);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_synced ON freshdesk_tickets(synced_at DESC);
