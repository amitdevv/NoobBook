"""
MCP Connection Service - Manage MCP server connections (account-level).

Educational Note: MCP connections are account-level integrations that can be
used in two ways:
1. As "MCP" sources — snapshot resources into the RAG pipeline
2. As live chat tools — MCP tools injected into Claude's tool list

Supports two transports:
- SSE: HTTP-based (server_url + auth_config)
- Stdio: Subprocess-based (command + args + env vars)

Security note:
- auth_config (tokens, keys) is masked before sending to frontend.
- stdio_config.env (API keys, domains) is masked before sending to frontend.
- Raw credentials are only loaded with include_secret=True (server-side only).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)

# Default user ID for single-user mode (matches backend/supabase/init.sql)
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"

VALID_AUTH_TYPES = {"none", "bearer", "api_key", "header"}
VALID_TRANSPORTS = {"sse", "stdio"}


class McpConnectionService:
    """
    CRUD + validation + tool caching for MCP server connections stored in Supabase.
    """

    TABLE = "mcp_connections"
    USERS_TABLE = "mcp_connection_users"

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
    def _mask_value(value: str) -> str:
        """Mask a single secret value for frontend display."""
        if len(value) > 6:
            return value[:3] + "***" + value[-3:]
        if len(value) > 0:
            return "***"
        return value

    @staticmethod
    def mask_auth_config(auth_type: str, auth_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Mask sensitive values in auth_config for safe frontend display."""
        if not auth_config or auth_type == "none":
            return None

        masked = {}
        for key, value in auth_config.items():
            if isinstance(value, str):
                masked[key] = McpConnectionService._mask_value(value)
            else:
                masked[key] = value
        return masked

    @staticmethod
    def mask_stdio_config(stdio_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Mask sensitive values in stdio_config for safe frontend display.

        Educational Note: stdio_config.env contains API keys and secrets
        (e.g., FRESHDESK_API_KEY). We mask these but keep command/args visible.
        """
        if not stdio_config:
            return None

        masked = {
            "command": stdio_config.get("command", ""),
            "args": stdio_config.get("args", []),
        }

        env = stdio_config.get("env")
        if env and isinstance(env, dict):
            masked["env_masked"] = {
                k: McpConnectionService._mask_value(v) if isinstance(v, str) else v
                for k, v in env.items()
            }

        return masked

    def _format_for_frontend(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Remove secrets and normalize output for frontend."""
        auth_type = row.get("auth_type", "none")
        auth_config = row.get("auth_config")
        stdio_config = row.get("stdio_config")
        transport = row.get("transport", "sse")

        # Extract tool summary from cached_tools (names + descriptions only)
        cached_tools = row.get("cached_tools")
        tool_summary = None
        if cached_tools and isinstance(cached_tools, list):
            tool_summary = [
                {"name": t.get("name", ""), "description": t.get("description", "")}
                for t in cached_tools
            ]

        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "description": row.get("description") or "",
            "server_url": row.get("server_url") or "",
            "transport": transport,
            "auth_type": auth_type,
            "auth_config_masked": self.mask_auth_config(auth_type, auth_config),
            "stdio_config": self.mask_stdio_config(stdio_config) if transport == "stdio" else None,
            "tools_enabled": bool(row.get("tools_enabled", False)),
            "cached_tools": tool_summary,
            "tools_cached_at": row.get("tools_cached_at"),
            "is_active": bool(row.get("is_active", True)),
            "visible_to_all": bool(row.get("visible_to_all", True)),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    # ---------------------------------------------------------------------
    # CRUD
    # ---------------------------------------------------------------------

    def list_connections(
        self, user_id: str = DEFAULT_USER_ID, is_admin: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all connections the user can access.
        Admins see ALL connections. Non-admins see owned + shared + visible_to_all.
        """
        if is_admin:
            all_resp = (
                self.supabase.table(self.TABLE)
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            return [self._format_for_frontend(row) for row in (all_resp.data or [])]

        # Non-admin: owned connections
        owned_resp = (
            self.supabase.table(self.TABLE)
            .select("*")
            .eq("owner_user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        connections = owned_resp.data or []
        privileged_ids: set = {c.get("id") for c in connections}

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
            privileged_ids.update(shared_ids)

        # Connections marked visible to all users
        visible_resp = (
            self.supabase.table(self.TABLE)
            .select("*")
            .eq("visible_to_all", True)
            .order("created_at", desc=True)
            .execute()
        )
        connections.extend(visible_resp.data or [])

        # Dedupe by id
        deduped: Dict[str, Dict[str, Any]] = {}
        for c in connections:
            cid = c.get("id")
            if cid:
                deduped[cid] = c

        results = []
        for row in deduped.values():
            formatted = self._format_for_frontend(row)
            if row.get("id") not in privileged_ids:
                formatted["auth_config_masked"] = None
            results.append(formatted)
        return results

    def get_connection(
        self,
        connection_id: str,
        user_id: str = DEFAULT_USER_ID,
        include_secret: bool = False,
        _server_internal: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single connection.

        Args:
            connection_id: The connection UUID
            user_id: Requesting user's ID (for access control)
            include_secret: If True, return the raw row with auth_config
            _server_internal: If True, skip user-level access control.
                Only used by server-side code (processor) that already
                runs with the service key.
        """
        if not connection_id:
            logger.warning("get_connection called with empty connection_id")
            return None

        try:
            resp = (
                self.supabase.table(self.TABLE)
                .select("*")
                .eq("id", connection_id)
                .execute()
            )
        except Exception as e:
            logger.error(
                "Supabase query failed for mcp connection_id=%s: %s",
                connection_id, e,
            )
            return None

        if not resp.data:
            logger.warning(
                "MCP connection not found: connection_id=%s", connection_id,
            )
            return None

        row = resp.data[0]

        # Server-internal calls skip access control (source already authorized at upload time)
        if _server_internal:
            return row

        # User-facing access control: owner, visible_to_all, or shared.
        if row.get("owner_user_id") != user_id:
            if row.get("visible_to_all"):
                pass
            else:
                shared = (
                    self.supabase.table(self.USERS_TABLE)
                    .select("id")
                    .eq("connection_id", connection_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                if not (shared.data or []):
                    logger.warning(
                        "Access denied for mcp connection_id=%s: "
                        "owner=%s, requester=%s, visible_to_all=%s",
                        connection_id,
                        row.get("owner_user_id"),
                        user_id,
                        row.get("visible_to_all"),
                    )
                    return None

        if include_secret:
            return row

        return self._format_for_frontend(row)

    def create_connection(
        self,
        name: str,
        transport: str = "sse",
        server_url: str = "",
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None,
        stdio_config: Optional[Dict[str, Any]] = None,
        description: str = "",
        tools_enabled: bool = False,
        user_id: str = DEFAULT_USER_ID,
    ) -> Dict[str, Any]:
        """Create a new MCP connection (SSE or stdio)."""
        if auth_type not in VALID_AUTH_TYPES:
            raise ValueError(f"auth_type must be one of {VALID_AUTH_TYPES}")
        if transport not in VALID_TRANSPORTS:
            raise ValueError(f"transport must be one of {VALID_TRANSPORTS}")

        insert_data: Dict[str, Any] = {
            "owner_user_id": user_id,
            "name": name,
            "description": description,
            "transport": transport,
            "auth_type": auth_type,
            "auth_config": auth_config or {},
            "is_active": True,
            "tools_enabled": tools_enabled,
        }

        if transport == "stdio":
            insert_data["stdio_config"] = stdio_config or {}
            insert_data["server_url"] = None
        else:
            insert_data["server_url"] = server_url
            insert_data["stdio_config"] = {}

        resp = self.supabase.table(self.TABLE).insert(insert_data).execute()
        if not resp.data:
            raise RuntimeError("Failed to create MCP connection")

        return self._format_for_frontend(resp.data[0])

    def delete_connection(self, connection_id: str, user_id: str = DEFAULT_USER_ID) -> bool:
        """Delete an MCP connection (owner only)."""
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

    def update_connection_visibility(
        self, connection_id: str, visible_to_all: bool
    ) -> Optional[Dict[str, Any]]:
        """Toggle whether a connection is visible to all users (admin only)."""
        resp = (
            self.supabase.table(self.TABLE)
            .update({"visible_to_all": visible_to_all})
            .eq("id", connection_id)
            .execute()
        )
        if not resp.data:
            return None
        return self._format_for_frontend(resp.data[0])

    # ---------------------------------------------------------------------
    # Tools management
    # ---------------------------------------------------------------------

    def update_tools_enabled(
        self, connection_id: str, enabled: bool
    ) -> Optional[Dict[str, Any]]:
        """Toggle whether this connection's tools are available in chat."""
        resp = (
            self.supabase.table(self.TABLE)
            .update({"tools_enabled": enabled})
            .eq("id", connection_id)
            .execute()
        )
        if not resp.data:
            return None
        return self._format_for_frontend(resp.data[0])

    def discover_tools(
        self, connection_id: str, user_id: str = DEFAULT_USER_ID
    ) -> List[Dict[str, Any]]:
        """
        Live-discover tools from an MCP server and cache the result.

        Educational Note: Makes a real-time call to the MCP server to list
        available tools, then caches the full tool definitions (including
        input_schema) in the cached_tools column for use during chat.
        """
        connection = self.get_connection(
            connection_id=connection_id,
            user_id=user_id,
            include_secret=True,
        )
        if not connection:
            raise ValueError("MCP connection not found")

        from app.services.integrations.mcp.mcp_client import list_tools

        tools = list_tools(
            server_url=connection.get("server_url") or "",
            auth_type=connection.get("auth_type", "none"),
            auth_config=connection.get("auth_config"),
            transport=connection.get("transport", "sse"),
            stdio_config=connection.get("stdio_config"),
        )

        # Cache the full tool definitions
        now = datetime.now(timezone.utc).isoformat()
        self.supabase.table(self.TABLE).update({
            "cached_tools": tools,
            "tools_cached_at": now,
        }).eq("id", connection_id).execute()

        return tools

    def get_tool_enabled_connections(
        self, user_id: str = DEFAULT_USER_ID
    ) -> List[Dict[str, Any]]:
        """
        Get all connections where tools_enabled=True that the user can access.

        Educational Note: Used by mcp_tool_service during chat to know which
        MCP servers should contribute tools to Claude's tool list.
        Returns raw rows (with secrets) for server-side tool execution.
        """
        # Get all tool-enabled connections
        resp = (
            self.supabase.table(self.TABLE)
            .select("*")
            .eq("tools_enabled", True)
            .eq("is_active", True)
            .execute()
        )

        if not resp.data:
            return []

        # Filter by user access (owner, visible_to_all, or shared)
        accessible = []
        needs_shared_check = []
        for row in resp.data:
            if row.get("owner_user_id") == user_id or row.get("visible_to_all"):
                accessible.append(row)
            else:
                needs_shared_check.append(row)

        # Batch-check shared access in a single query instead of N+1
        if needs_shared_check:
            candidate_ids = [r["id"] for r in needs_shared_check]
            shared_resp = (
                self.supabase.table(self.USERS_TABLE)
                .select("connection_id")
                .eq("user_id", user_id)
                .in_("connection_id", candidate_ids)
                .execute()
            )
            shared_set = {r["connection_id"] for r in (shared_resp.data or [])}
            for row in needs_shared_check:
                if row["id"] in shared_set:
                    accessible.append(row)

        return accessible

    # ---------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------

    def validate_connection(
        self,
        transport: str = "sse",
        server_url: str = "",
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None,
        stdio_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate an MCP server connection by attempting to initialize a session.
        Supports both SSE and stdio transports.
        """
        from app.services.integrations.mcp.mcp_client import validate_connection as mcp_validate

        if transport not in VALID_TRANSPORTS:
            return {"valid": False, "message": f"transport must be one of {VALID_TRANSPORTS}"}

        if transport == "sse" and not server_url:
            return {"valid": False, "message": "server_url is required for SSE transport"}

        if transport == "stdio":
            cfg = stdio_config or {}
            if not cfg.get("command"):
                return {"valid": False, "message": "command is required for stdio transport"}

        if auth_type not in VALID_AUTH_TYPES:
            return {"valid": False, "message": f"auth_type must be one of {VALID_AUTH_TYPES}"}

        result = mcp_validate(
            server_url=server_url,
            auth_type=auth_type,
            auth_config=auth_config,
            transport=transport,
            stdio_config=stdio_config,
        )

        if result.get("valid"):
            tool_count = result.get("tool_count", 0)
            resource_count = result.get("resource_count", 0)
            msg = f"Connected successfully ({tool_count} tools, {resource_count} resources)"
            return {"valid": True, "message": msg}

        return {"valid": False, "message": result.get("error", "Connection failed")}


# Singleton instance
mcp_connection_service = McpConnectionService()
