"""
Freshdesk Executor - Runs SQL queries against the local freshdesk_tickets table.

Educational Note: Unlike database_executor which connects to external databases,
this executor queries the local Supabase PostgreSQL directly since Freshdesk
tickets are synced into a local table. Always scopes queries by source_id.
"""

import logging
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

UNSAFE_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

FRESHDESK_SCHEMA = """
freshdesk_tickets table columns:
- ticket_id (BIGINT): Freshdesk ticket ID
- subject (TEXT): Ticket subject
- description_text (TEXT): Ticket body
- status (TEXT): Open, Pending, Resolved, Closed, Waiting on Customer, Waiting on Third Party
- priority (TEXT): Low, Medium, High, Urgent
- ticket_type (TEXT): Ticket category type
- source_channel (TEXT): Email, Portal, Phone, Chat, etc.
- requester_name (TEXT), requester_email (TEXT)
- agent_name (TEXT), agent_email (TEXT)
- group_name (TEXT), product_name (TEXT), company_name (TEXT)
- category (TEXT), subcategory (TEXT), tags (TEXT[])
- ticket_created_at (TIMESTAMPTZ), ticket_updated_at (TIMESTAMPTZ)
- due_by (TIMESTAMPTZ), resolved_at (TIMESTAMPTZ), closed_at (TIMESTAMPTZ)
- first_responded_at (TIMESTAMPTZ)
- resolution_time_hours (NUMERIC), first_response_time_hours (NUMERIC)
- is_escalated (BOOLEAN), custom_fields (JSONB)
"""


class FreshdeskExecutor:
    """Executes Freshdesk agent tools against the local freshdesk_tickets table."""

    def __init__(self):
        self._conn = None

    def _get_connection_string(self) -> str:
        """Get PostgreSQL connection string for local Supabase."""
        db_url = os.getenv("SUPABASE_DB_URL")
        if db_url:
            return db_url
        host = os.getenv("POSTGRES_HOST", "supabase-db")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        return f"postgresql://postgres:{password}@{host}:{port}/{db}"

    def _get_connection(self):
        """Get or create a psycopg2 connection."""
        if self._conn and not self._conn.closed:
            try:
                self._conn.cursor().execute("SELECT 1")
                return self._conn
            except Exception:
                self._conn = None
        self._conn = psycopg2.connect(self._get_connection_string(), connect_timeout=5)
        self._conn.autocommit = True
        return self._conn

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def validate_connection(self) -> bool:
        """Check if we can connect to the database."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return True
        except Exception as e:
            logger.error("Freshdesk executor: DB connection failed: %s", e)
            return False

    def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any],
        project_id: str, source_id: str,
    ) -> Tuple[Dict[str, Any], bool]:
        """Execute a Freshdesk agent tool. Returns (result, is_termination)."""
        if tool_name == "schema_info":
            return self._schema_info(source_id), False
        elif tool_name == "query_runner":
            return self._query_runner(tool_input, source_id), False
        elif tool_name == "return_ticket_analysis":
            return tool_input, True
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}, False

    def _schema_info(self, source_id: str) -> Dict[str, Any]:
        """Return the freshdesk_tickets schema and ticket count for this source."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) as cnt FROM freshdesk_tickets WHERE source_id = %s",
                (source_id,),
            )
            row = cur.fetchone()
            count = row[0] if row else 0
            cur.close()
            return {
                "success": True,
                "schema": FRESHDESK_SCHEMA.strip(),
                "ticket_count": count,
                "source_id": source_id,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _query_runner(self, tool_input: Dict[str, Any], source_id: str) -> Dict[str, Any]:
        """Execute a read-only SQL query scoped to the source_id."""
        sql = (tool_input.get("sql_query") or "").strip()
        if not sql:
            return {"success": False, "error": "sql_query is required"}

        # Validate read-only
        if UNSAFE_SQL_RE.search(sql):
            return {"success": False, "error": "Only SELECT queries are allowed"}

        # Must reference freshdesk_tickets
        if "freshdesk_tickets" not in sql.lower():
            return {"success": False, "error": "Query must reference freshdesk_tickets table"}

        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Set query timeout
            cur.execute("SET statement_timeout = 10000")

            # Inject source_id filter
            # If WHERE exists, add AND; otherwise add WHERE
            scoped_sql = self._inject_source_filter(sql, source_id)

            start = time.time()
            cur.execute(scoped_sql)
            rows = cur.fetchmany(100)
            elapsed = round((time.time() - start) * 1000, 1)

            results = [dict(r) for r in rows]
            column_names = [desc[0] for desc in cur.description] if cur.description else []

            cur.close()

            return {
                "success": True,
                "query": scoped_sql,
                "row_count": len(results),
                "results": results,
                "column_names": column_names,
                "execution_time_ms": elapsed,
                "truncated": cur.rowcount > 100 if cur.rowcount and cur.rowcount > 0 else False,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "query": sql}

    def _inject_source_filter(self, sql: str, source_id: str) -> str:
        """Inject WHERE source_id = ... into the query for data isolation."""
        filter_clause = f"source_id = \'{source_id}\'"

        # Simple heuristic: find WHERE and add AND, or add WHERE before GROUP/ORDER/LIMIT
        sql_lower = sql.lower()
        if "where" in sql_lower:
            # Add AND after WHERE
            where_idx = sql_lower.index("where") + 5
            return sql[:where_idx] + f" {filter_clause} AND" + sql[where_idx:]
        else:
            # Find the first GROUP BY, ORDER BY, LIMIT, or end of query
            for keyword in ["group by", "order by", "limit", "having"]:
                if keyword in sql_lower:
                    idx = sql_lower.index(keyword)
                    return sql[:idx] + f" WHERE {filter_clause} " + sql[idx:]
            # No clauses found, append WHERE at the end
            return sql.rstrip(";") + f" WHERE {filter_clause}"


freshdesk_executor = FreshdeskExecutor()
