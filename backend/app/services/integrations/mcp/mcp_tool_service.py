"""
MCP Tool Service - Orchestrates MCP tools in chat conversations.

Educational Note: This service follows the knowledge_base_service pattern to
provide MCP tools to Claude during chat. It:

1. Discovers available MCP tools from user's tool-enabled connections
2. Converts them to Claude-compatible tool definitions with namespaced names
3. Routes tool execution to the correct MCP server via mcp_client

Tool Namespacing:
MCP tools are prefixed with `mcp_{slug}_` to avoid collision with built-in
tools (search_sources, store_memory, etc.) and between multiple MCP servers.
For example, a Freshdesk MCP server's "create_ticket" tool becomes
"mcp_freshdesk_create_ticket".

Lifecycle:
Each tool call spawns a fresh MCP connection (SSE HTTP request or stdio subprocess).
This is intentionally stateless — no persistent connections to manage.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# All MCP tool names start with this prefix
MCP_TOOL_PREFIX = "mcp_"


def _slugify(name: str) -> str:
    """Convert a connection name to a safe slug for tool namespacing."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower().strip())
    return slug.strip("_") or "mcp"


class McpToolService:
    """
    Orchestrator for MCP tools in chat, following the knowledge_base_service pattern.

    Educational Note: This service is called by main_chat_service to:
    - get_available_tools(): Returns Claude-format tool definitions
    - can_handle(tool_name): Checks if a tool is an MCP tool
    - execute(tool_name, tool_input): Calls the MCP server and returns result
    """

    def get_available_tools(self, user_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[str, str]]]:
        """
        Get all MCP tools available for chat, formatted for Claude API.

        Educational Note: Loads cached tools from all tools_enabled connections
        accessible to the user. Returns Claude-format tool definitions with
        namespaced names, plus a registry mapping namespaced names back to
        (connection_id, original_tool_name) for execution routing.

        Args:
            user_id: The requesting user's ID

        Returns:
            Tuple of:
            - List of Claude tool definitions
            - Registry dict: {namespaced_name: (connection_id, original_name)}
        """
        from app.services.data_services.mcp_connection_service import mcp_connection_service

        connections = mcp_connection_service.get_tool_enabled_connections(user_id=user_id)

        if not connections:
            return [], {}

        tools: List[Dict[str, Any]] = []
        registry: Dict[str, Tuple[str, str]] = {}

        for conn in connections:
            cached_tools = conn.get("cached_tools")
            if not cached_tools or not isinstance(cached_tools, list):
                continue

            connection_id = conn.get("id", "")
            connection_name = conn.get("name", "MCP")
            slug = _slugify(connection_name)

            for tool_def in cached_tools:
                original_name = tool_def.get("name", "")
                if not original_name:
                    continue

                # Namespace the tool name to avoid collisions
                namespaced = f"{MCP_TOOL_PREFIX}{slug}_{original_name}"

                # Build Claude-compatible tool definition
                description = tool_def.get("description", "")
                source_hint = f" (via {connection_name} MCP)"
                claude_tool = {
                    "name": namespaced,
                    "description": (description + source_hint) if description else f"MCP tool from {connection_name}",
                    "input_schema": tool_def.get("input_schema", {"type": "object", "properties": {}}),
                }

                tools.append(claude_tool)
                registry[namespaced] = (connection_id, original_name)

        return tools, registry

    def can_handle(self, tool_name: str) -> bool:
        """Check if a tool name is an MCP tool (starts with 'mcp_')."""
        return tool_name.startswith(MCP_TOOL_PREFIX)

    def execute(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        registry: Dict[str, Tuple[str, str]],
    ) -> str:
        """
        Execute an MCP tool call and return the result text.

        Educational Note: Looks up the connection and original tool name from
        the registry, loads the connection's secrets, then calls mcp_client.call_tool()
        which spawns a fresh connection to the MCP server.

        Args:
            tool_name: The namespaced tool name (e.g., mcp_freshdesk_create_ticket)
            tool_input: Arguments from Claude's tool call
            registry: The registry from get_available_tools()

        Returns:
            Result text to send back to Claude
        """
        if tool_name not in registry:
            return f"Error: Unknown MCP tool '{tool_name}'"

        connection_id, original_name = registry[tool_name]

        # Load connection with secrets for tool execution
        from app.services.data_services.mcp_connection_service import mcp_connection_service

        connection = mcp_connection_service.get_connection(
            connection_id=connection_id,
            include_secret=True,
            _server_internal=True,
        )
        if not connection:
            return f"Error: MCP connection not found for tool '{tool_name}'"

        logger.info(
            "Executing MCP tool: %s (original: %s, connection: %s)",
            tool_name, original_name, connection.get("name", connection_id),
        )

        try:
            from app.services.integrations.mcp.mcp_client import call_tool

            result = call_tool(
                tool_name=original_name,
                arguments=tool_input,
                server_url=connection.get("server_url") or "",
                auth_type=connection.get("auth_type", "none"),
                auth_config=connection.get("auth_config"),
                transport=connection.get("transport", "sse"),
                stdio_config=connection.get("stdio_config"),
            )

            return result

        except Exception as e:
            logger.error("MCP tool execution failed for %s: %s", tool_name, e)
            return f"Error executing MCP tool '{original_name}': {str(e)}"


# Singleton instance
mcp_tool_service = McpToolService()
