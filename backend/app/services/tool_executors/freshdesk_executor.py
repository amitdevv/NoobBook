"""
Freshdesk Executor - Runs SQL queries against the global freshdesk_tickets table.

Educational Note: Unlike database_executor which connects to external databases,
this executor queries the local Supabase PostgreSQL directly since Freshdesk
tickets are synced into a global table. All tickets belong to the same Freshdesk
account, so no per-source scoping is needed.
"""

import logging
import os
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

UNSAFE_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

FRESHDESK_SCHEMA = """
freshdesk_tickets table columns:
- ticket_id (BIGINT): Freshdesk ticket ID (unique)
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


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert non-JSON-serializable types (datetime, Decimal) to strings."""
    for key, val in row.items():
        if isinstance(val, (datetime, date)):
            row[key] = val.isoformat()
        elif isinstance(val, Decimal):
            row[key] = float(val)
    return row


class FreshdeskExecutor:
    """Executes Freshdesk agent tools against the global freshdesk_tickets table."""

    def __init__(self):
        self._conn = None

    def _get_connection_string(self) -> str:
        """Get PostgreSQL connection string for local Supabase.
        Prefers SUPABASE_DB_URL env var, falls back to constructing from parts."""
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
        conn_str = self._get_connection_string()
        logger.info("Freshdesk executor connecting to: %s",
                     conn_str.split("@")[-1] if "@" in conn_str else "unknown")
        self._conn = psycopg2.connect(conn_str, connect_timeout=5)
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
            return self._schema_info(), False
        elif tool_name == "query_runner":
            return self._query_runner(tool_input), False
        elif tool_name == "return_ticket_analysis":
            return tool_input, True
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}, False

    def _schema_info(self) -> Dict[str, Any]:
        """Return the freshdesk_tickets schema and global ticket count."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM freshdesk_tickets")
            row = cur.fetchone()
            count = row[0] if row else 0
            cur.close()
            return {
                "success": True,
                "schema": FRESHDESK_SCHEMA.strip(),
                "ticket_count": count,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _query_runner(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a read-only SQL query against the global freshdesk_tickets table."""
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

            start = time.time()
            cur.execute(sql)
            rows = cur.fetchmany(100)
            elapsed = round((time.time() - start) * 1000, 1)

            results = [_serialize_row(dict(r)) for r in rows]
            column_names = [desc[0] for desc in cur.description] if cur.description else []
            truncated = len(results) == 100

            cur.close()

            result = {
                "success": True,
                "query": sql,
                "row_count": len(results),
                "results": results,
                "column_names": column_names,
                "execution_time_ms": elapsed,
                "truncated": truncated,
            }
            if truncated:
                result["warning"] = "Results limited to 100 rows. Use GROUP BY, COUNT, or LIMIT to get aggregated data."
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "query": sql}


freshdesk_executor = FreshdeskExecutor()
