-- ============================================================================
-- FRESHDESK TICKETS TABLE
-- Stores synced Freshdesk ticket data for SQL-based analysis in chat.
-- Each row is scoped to a source_id (one Freshdesk source per project).
-- ============================================================================

CREATE TABLE IF NOT EXISTS freshdesk_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  ticket_id BIGINT NOT NULL,

  -- Core ticket fields
  subject TEXT,
  description_text TEXT,
  status TEXT,
  priority TEXT,
  ticket_type TEXT,
  source_channel TEXT,

  -- People
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

  -- Classification
  category TEXT,
  subcategory TEXT,
  tags TEXT[] DEFAULT '{}',

  -- Timestamps (from Freshdesk)
  ticket_created_at TIMESTAMPTZ,
  ticket_updated_at TIMESTAMPTZ,
  due_by TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  first_responded_at TIMESTAMPTZ,

  -- Computed metrics
  resolution_time_hours NUMERIC(10, 2),
  first_response_time_hours NUMERIC(10, 2),
  is_escalated BOOLEAN DEFAULT false,

  -- Flexible storage
  custom_fields JSONB DEFAULT '{}'::jsonb,

  -- Sync metadata
  synced_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Upsert constraint: one row per ticket per source
  CONSTRAINT freshdesk_tickets_source_ticket_unique UNIQUE (source_id, ticket_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_source_id ON freshdesk_tickets(source_id);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_project_id ON freshdesk_tickets(project_id);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_status ON freshdesk_tickets(source_id, status);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_created ON freshdesk_tickets(source_id, ticket_created_at DESC);
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_agent ON freshdesk_tickets(source_id, agent_name);

-- Auto-update updated_at timestamp
CREATE TRIGGER update_freshdesk_tickets_updated_at
  BEFORE UPDATE ON freshdesk_tickets
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
