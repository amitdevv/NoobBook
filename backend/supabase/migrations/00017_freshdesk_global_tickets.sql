-- ============================================================================
-- FRESHDESK TICKETS: GLOBAL DATA STORE
-- Migrate from per-source ticket storage to global ticket storage.
-- Tickets are now keyed by ticket_id alone (one Freshdesk account = one pool).
-- source_id and project_id become nullable tracking fields.
-- ============================================================================

-- 1. Drop the old per-source unique constraint
ALTER TABLE freshdesk_tickets
  DROP CONSTRAINT IF EXISTS freshdesk_tickets_source_ticket_unique;

-- 2. Make source_id and project_id nullable (tickets are global now)
ALTER TABLE freshdesk_tickets
  ALTER COLUMN source_id DROP NOT NULL,
  ALTER COLUMN project_id DROP NOT NULL;

-- 3. Drop the foreign key on source_id (tickets outlive individual sources)
ALTER TABLE freshdesk_tickets
  DROP CONSTRAINT IF EXISTS freshdesk_tickets_source_id_fkey;

-- 4. Drop the foreign key on project_id (same reason)
ALTER TABLE freshdesk_tickets
  DROP CONSTRAINT IF EXISTS freshdesk_tickets_project_id_fkey;

-- 5. Add global unique constraint on ticket_id alone
ALTER TABLE freshdesk_tickets
  ADD CONSTRAINT freshdesk_tickets_ticket_unique UNIQUE (ticket_id);

-- 6. Drop old source-scoped indexes (no longer useful)
DROP INDEX IF EXISTS idx_freshdesk_tickets_source_id;
DROP INDEX IF EXISTS idx_freshdesk_tickets_status;
DROP INDEX IF EXISTS idx_freshdesk_tickets_created;
DROP INDEX IF EXISTS idx_freshdesk_tickets_agent;

-- 7. Create new global indexes
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_status_global ON freshdesk_tickets(status);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_created_global ON freshdesk_tickets(ticket_created_at DESC);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_agent_global ON freshdesk_tickets(agent_name);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_synced ON freshdesk_tickets(synced_at DESC);
