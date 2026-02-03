"""
Database Connection Service - Manage external database connections (Postgres/MySQL).

Educational Note: These connections are *account-level* integrations that can be
attached to projects as "DATABASE" sources. The actual connection string is stored
in Supabase for self-hosted deployments.

Security note:
- We never return the full connection URI to the frontend.
- The frontend only receives a masked URI for display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import psycopg2
import pymysql

from app.services.integrations.supabase import get_supabase, is_supabase_enabled


# Default user ID for single-user mode (matches backend/supabase/init.sql)
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


@dataclass(frozen=True)
class DatabaseConnection:
    """Typed representation of a database connection row."""

    id: str
    owner_user_id: str
    name: str
    description: str
    db_type: str  # "postgresql" | "mysql"
    connection_uri: str
    is_active: bool
    created_at: str
    updated_at: str


class DatabaseConnectionService:
    """
    CRUD + validation for external database connections stored in Supabase.
    """

    TABLE = "database_connections"
    USERS_TABLE = "database_connection_users"

    def __init__(self) -> None:
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) to your .env file."
            )
        self.supabase = get_supabase()

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def mask_connection_uri(connection_uri: str) -> str:
        """
        Mask password in a connection URI for safe display.

        Example:
            postgresql://user:pass@host:5432/db -> postgresql://user:***@host:5432/db
        """
        if not connection_uri:
            return ""

        parsed = urlparse(connection_uri)

        # If no username present, nothing to mask
        if not parsed.username:
            return connection_uri

        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        user = parsed.username or ""

        # Only mask if a password was provided
        password_part = ":***" if parsed.password else ""
        netloc = f"{user}{password_part}@{host}{port}"

        return urlunparse(
            (
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )

    def _format_for_frontend(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Remove secrets and normalize output for frontend."""
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "description": row.get("description") or "",
            "db_type": row.get("db_type"),
            "connection_uri_masked": self.mask_connection_uri(row.get("connection_uri", "")),
            "is_active": bool(row.get("is_active", True)),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    # ---------------------------------------------------------------------
    # CRUD
    # ---------------------------------------------------------------------

    def list_connections(self, user_id: str = DEFAULT_USER_ID) -> List[Dict[str, Any]]:
        """List all connections the user can access (owner + shared)."""
        owned_resp = (
            self.supabase.table(self.TABLE)
            .select("*")
            .eq("owner_user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        connections = owned_resp.data or []

        # Shared connections (multi-user mode)
        shared_resp = (
            self.supabase.table(self.USERS_TABLE)
            .select("connection_id")
            .eq("user_id", user_id)
            .execute()
        )
        shared_ids = [r.get("connection_id") for r in (shared_resp.data or []) if r.get("connection_id")]

        if shared_ids:
            shared_connections_resp = (
                self.supabase.table(self.TABLE)
                .select("*")
                .in_("id", shared_ids)
                .order("created_at", desc=True)
                .execute()
            )
            connections.extend(shared_connections_resp.data or [])

        # Dedupe by id
        deduped: Dict[str, Dict[str, Any]] = {}
        for c in connections:
            cid = c.get("id")
            if cid:
                deduped[cid] = c

        return [self._format_for_frontend(row) for row in deduped.values()]

    def get_connection(
        self,
        connection_id: str,
        user_id: str = DEFAULT_USER_ID,
        include_secret: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single connection.

        If include_secret=False, the connection URI is masked.
        """
        resp = (
            self.supabase.table(self.TABLE)
            .select("*")
            .eq("id", connection_id)
            .execute()
        )
        if not resp.data:
            return None

        row = resp.data[0]

        # Owner check (single-user mode). For shared connections, row-level security
        # should enforce access in multi-user mode.
        if row.get("owner_user_id") != user_id:
            # Allow if shared
            shared = (
                self.supabase.table(self.USERS_TABLE)
                .select("id")
                .eq("connection_id", connection_id)
                .eq("user_id", user_id)
                .execute()
            )
            if not (shared.data or []):
                return None

        if include_secret:
            return row

        return self._format_for_frontend(row)

    def create_connection(
        self,
        name: str,
        db_type: str,
        connection_uri: str,
        description: str = "",
        user_id: str = DEFAULT_USER_ID,
    ) -> Dict[str, Any]:
        """Create a new database connection."""
        if db_type not in {"postgresql", "mysql"}:
            raise ValueError("db_type must be 'postgresql' or 'mysql'")

        insert_data = {
            "owner_user_id": user_id,
            "name": name,
            "description": description,
            "db_type": db_type,
            "connection_uri": connection_uri,
            "is_active": True,
        }

        resp = self.supabase.table(self.TABLE).insert(insert_data).execute()
        if not resp.data:
            raise RuntimeError("Failed to create database connection")

        return self._format_for_frontend(resp.data[0])

    def delete_connection(self, connection_id: str, user_id: str = DEFAULT_USER_ID) -> bool:
        """Delete a database connection (owner only)."""
        existing = (
            self.supabase.table(self.TABLE)
            .select("id")
            .eq("id", connection_id)
            .eq("owner_user_id", user_id)
            .execute()
        )
        if not existing.data:
            return False

        self.supabase.table(self.TABLE).delete().eq("id", connection_id).execute()
        return True

    # ---------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------

    def validate_connection(self, db_type: str, connection_uri: str) -> Dict[str, Any]:
        """
        Validate connection credentials by running a minimal query.
        """
        if db_type not in {"postgresql", "mysql"}:
            return {"valid": False, "message": "db_type must be 'postgresql' or 'mysql'"}

        if not connection_uri:
            return {"valid": False, "message": "connection_uri is required"}

        try:
            if db_type == "postgresql":
                conn = psycopg2.connect(connection_uri, connect_timeout=5)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    cur.fetchone()
                    cur.close()
                finally:
                    conn.close()
                return {"valid": True, "message": "PostgreSQL connection successful"}

            # MySQL
            parsed = urlparse(connection_uri)
            if not parsed.hostname:
                return {"valid": False, "message": "Invalid MySQL connection URI"}

            conn = pymysql.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=parsed.username,
                password=parsed.password,
                database=(parsed.path or "").lstrip("/") or None,
                connect_timeout=5,
                read_timeout=10,
                write_timeout=10,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 as ok")
                    cur.fetchone()
            finally:
                conn.close()

            return {"valid": True, "message": "MySQL connection successful"}

        except Exception as e:
            return {"valid": False, "message": str(e)}


# Singleton instance
database_connection_service = DatabaseConnectionService()

