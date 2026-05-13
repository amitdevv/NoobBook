-- Migration: exec_freshdesk_query — strip string literals before keyword check
-- Created: 2026-05-13
--
-- Issue: prod logs show legitimate SELECTs being rejected with
--   "Only SELECT queries are allowed"   (code P0001)
-- when the user's question mentions a topic whose generated SQL contains
-- a write-keyword as a word inside a string literal. Example trigger:
--   WHERE description ILIKE '%customer asked to update plan%'
-- — the `update` inside the quoted pattern matches the defense-in-depth
-- regex and the whole query is aborted before it reaches the planner.
-- Each false positive costs the agent one full iteration (Claude call +
-- retry).
--
-- Fix: strip string literals, quoted identifiers, and SQL comments BEFORE
-- running the keyword regex. The keyword check still rejects mutating
-- statements (we ONLY removed string contents from the input being
-- scanned); the actual query passed to EXECUTE is unchanged.
--
-- Also: bump the per-call statement_timeout to 30s. The previous
-- function had no SET, so it inherited the role default (~8s on managed
-- Supabase). Some analytical queries on 10k+ ticket tables push past 8s.
--
-- Dollar-quoted strings are used for the regex patterns ($$...$$) so we
-- don't have to nest SQL escapes for single quotes — the previous draft
-- of this migration had `''(''|[^''])*''` which is ambiguous between
-- "escape the outer SQL string" and "match a literal pair of quotes".

CREATE OR REPLACE FUNCTION public.exec_freshdesk_query(sql_query text)
RETURNS jsonb
LANGUAGE plpgsql
AS $func$
DECLARE
  cleaned_query text;
  stripped text;
  result jsonb;
BEGIN
  -- Trailing semicolons would break the wrapping subquery below.
  cleaned_query := regexp_replace(sql_query, ';\s*$', '');

  -- Build a string-stripped view of the query for the safety checks only.
  -- Order matters: comments first (so a `-- DROP TABLE` line doesn't
  -- survive into the next pass), then strings/identifiers. The output
  -- is used ONLY for keyword/table-name validation; the original
  -- `cleaned_query` (with strings intact) is what we actually execute.
  stripped := cleaned_query;
  stripped := regexp_replace(stripped, $re$/\*.*?\*/$re$, '', 'g');
  stripped := regexp_replace(stripped, $re$--[^\n]*$re$, '', 'g');
  -- Single-quoted strings with SQL-standard '' escape.
  stripped := regexp_replace(stripped, $re$'(?:''|[^'])*'$re$, $re$''$re$, 'g');
  -- Double-quoted identifiers with "" escape.
  stripped := regexp_replace(stripped, $re$"(?:""|[^"])*"$re$, $re$""$re$, 'g');

  IF stripped ~* $re$\m(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE|VACUUM|COPY|REINDEX|CLUSTER|REFRESH|LOCK|SECURITY)\M$re$ THEN
    RAISE EXCEPTION 'Only SELECT queries are allowed';
  END IF;

  IF position('freshdesk_tickets' in lower(stripped)) = 0 THEN
    RAISE EXCEPTION 'Query must reference the freshdesk_tickets table';
  END IF;

  -- Per-call statement timeout. SET LOCAL via set_config(..., true)
  -- scopes to the current transaction (the implicit txn around this
  -- function call), so the session default isn't mutated.
  PERFORM set_config('statement_timeout', '30000', true);

  -- LIMIT 100 cap matches the psycopg2 path's fetchmany(100) so a runaway
  -- query can't pull a 50k-row result back through PostgREST.
  EXECUTE format(
    'SELECT coalesce(jsonb_agg(to_jsonb(t)), ''[]''::jsonb) FROM (SELECT * FROM (%s) sub_q LIMIT 100) t',
    cleaned_query
  ) INTO result;

  RETURN COALESCE(result, '[]'::jsonb);
END;
$func$;

GRANT EXECUTE ON FUNCTION public.exec_freshdesk_query(text)
  TO service_role, authenticator, authenticated;
