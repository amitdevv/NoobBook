-- Migration: composite indexes for the freshdesk analyzer agent.
-- Created: 2026-04-28
--
-- The single-column indexes from migration 00017 cover lookups by status,
-- ticket_created_at, agent_name, and synced_at independently. The
-- agent's most common queries combine those filters — e.g.
-- "Resolved tickets in the last 30 days" or "Per-agent counts by status"
-- — and Postgres can't satisfy them efficiently with separate B-trees.
-- These composite indexes match the pmaibot reference schema and let the
-- analyzer's typical aggregations stay fast as the table grows.
--
-- All indexes use IF NOT EXISTS so re-runs are safe; CONCURRENTLY isn't
-- used because Supabase migrations run inside a transaction.

CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_status_created
  ON freshdesk_tickets (status, ticket_created_at DESC);

CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_priority_status
  ON freshdesk_tickets (priority, status);

CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_agent_status
  ON freshdesk_tickets (agent_name, status);

-- Resolution-time analytics frequently filter on resolved_at IS NOT NULL
-- with a date range. Partial index keeps it small (only resolved rows).
CREATE INDEX IF NOT EXISTS idx_freshdesk_tickets_resolved_created
  ON freshdesk_tickets (ticket_created_at DESC)
  WHERE resolved_at IS NOT NULL;
