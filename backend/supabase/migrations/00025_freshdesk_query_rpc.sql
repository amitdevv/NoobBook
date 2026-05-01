-- Migration: RPC for the Freshdesk analyzer's query_runner tool.
-- Created: 2026-05-01
--
-- The analyzer agent generates dynamic SELECT statements against
-- freshdesk_tickets and used to execute them via psycopg2 with
-- SUPABASE_DB_URL. That fails in deployments where the backend talks
-- to Supabase only through the API gateway (Coolify, separately-hosted
-- Supabase, managed Supabase) and never gets a direct route to the
-- Postgres container.
--
-- This RPC routes the same query through PostgREST/Kong, which the
-- backend already authenticates to with SUPABASE_SERVICE_KEY for every
-- other table call. No new env vars required for the operator.
--
-- Defense-in-depth: the Python executor validates SELECT-only and
-- the freshdesk_tickets reference before calling. The function repeats
-- those checks server-side so a future caller can't sidestep them by
-- bypassing the executor.
--
-- SECURITY INVOKER (the default) means the dynamic EXECUTE runs with
-- the *caller's* privileges, not the function-owner's. Calling with
-- the service_role key is what gives it full read access to the
-- table; an anon caller would simply get permission-denied on the
-- inner SELECT, which is the desired outcome.

CREATE OR REPLACE FUNCTION public.exec_freshdesk_query(sql_query text)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  cleaned_query text;
  result jsonb;
BEGIN
  -- Trailing semicolons would break the wrapping subquery below.
  cleaned_query := regexp_replace(sql_query, ';\s*$', '');

  -- Reject any statement that contains a mutating keyword. Conservative
  -- — false positives (e.g. INSERT inside a string literal) are safe;
  -- false negatives are not.
  IF cleaned_query ~* '\m(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE|VACUUM|COPY|REINDEX|CLUSTER|REFRESH|LOCK|SECURITY)\M' THEN
    RAISE EXCEPTION 'Only SELECT queries are allowed';
  END IF;

  IF position('freshdesk_tickets' in lower(cleaned_query)) = 0 THEN
    RAISE EXCEPTION 'Query must reference the freshdesk_tickets table';
  END IF;

  -- LIMIT 100 cap matches the psycopg2 path's fetchmany(100) so a runaway
  -- query can't pull a 50k-row result back through PostgREST. Wrapping
  -- as `SELECT * FROM (<query>) sub LIMIT 100` is valid for plain SELECT,
  -- ORDER BY, GROUP BY, and CTE (`WITH ... SELECT`) shapes the agent
  -- generates.
  EXECUTE format(
    'SELECT coalesce(jsonb_agg(to_jsonb(t)), ''[]''::jsonb) FROM (SELECT * FROM (%s) sub_q LIMIT 100) t',
    cleaned_query
  ) INTO result;

  RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

-- service_role is what the backend uses with SUPABASE_SERVICE_KEY.
-- authenticated/authenticator are granted so the function is callable
-- through whichever JWT role PostgREST resolves to in deployments that
-- proxy with a different key.
GRANT EXECUTE ON FUNCTION public.exec_freshdesk_query(text)
  TO service_role, authenticator, authenticated;
