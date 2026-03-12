"""
MCP connection management endpoints (account-level).

Educational Note: MCP connections are integrations that can be used as:
1. "MCP" sources — snapshot resources into the RAG pipeline
2. Live chat tools — MCP tools injected into Claude's tool list

Supports SSE (HTTP) and stdio (subprocess) transports.

Routes:
- GET    /settings/mcp                          - List MCP connections (masked)
- POST   /settings/mcp                          - Create an MCP connection
- DELETE /settings/mcp/<id>                     - Delete an MCP connection
- PATCH  /settings/mcp/<id>/visibility          - Toggle visible_to_all (admin only)
- POST   /settings/mcp/validate                 - Validate connection without saving
- GET    /settings/mcp/<id>/resources           - List available resources (live call)
- GET    /settings/mcp/<id>/tools               - Discover tools (live call + cache)
- POST   /settings/mcp/<id>/refresh-tools       - Force refresh cached tools
- PATCH  /settings/mcp/<id>/tools-enabled       - Toggle tools in chat
"""

from flask import jsonify, request, current_app

from app.api.settings import settings_bp
from app.services.auth.rbac import require_admin, get_request_identity
from app.services.data_services.mcp_connection_service import mcp_connection_service, DEFAULT_USER_ID


@settings_bp.route("/settings/mcp", methods=["GET"])
def list_mcp_connections():
    """List MCP connections available to the current user (masked)."""
    try:
        identity = get_request_identity()
        user_id = DEFAULT_USER_ID if not identity.is_authenticated else identity.user_id
        connections = mcp_connection_service.list_connections(
            user_id=user_id, is_admin=identity.is_admin
        )
        return jsonify({"success": True, "connections": connections, "count": len(connections)}), 200
    except Exception as e:
        current_app.logger.error(f"Error listing MCP connections: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/mcp", methods=["POST"])
@require_admin
def create_mcp_connection():
    """Create a new MCP connection (SSE or stdio)."""
    try:
        data = request.get_json() or {}

        name = (data.get("name") or "").strip()
        transport = (data.get("transport") or "sse").strip()
        server_url = (data.get("server_url") or "").strip()
        auth_type = (data.get("auth_type") or "none").strip()
        auth_config = data.get("auth_config") or {}
        stdio_config = data.get("stdio_config") or {}
        description = (data.get("description") or "").strip()
        tools_enabled = bool(data.get("tools_enabled", False))

        if not name:
            return jsonify({"success": False, "error": "name is required"}), 400
        if transport == "sse" and not server_url:
            return jsonify({"success": False, "error": "server_url is required for SSE transport"}), 400
        if transport == "stdio" and not stdio_config.get("command"):
            return jsonify({"success": False, "error": "command is required for stdio transport"}), 400

        # Validate before saving
        validation = mcp_connection_service.validate_connection(
            transport=transport,
            server_url=server_url,
            auth_type=auth_type,
            auth_config=auth_config,
            stdio_config=stdio_config,
        )
        if not validation.get("valid"):
            return jsonify({"success": False, "error": validation.get("message", "Validation failed")}), 400

        identity = get_request_identity()
        created = mcp_connection_service.create_connection(
            name=name,
            transport=transport,
            server_url=server_url,
            auth_type=auth_type,
            auth_config=auth_config,
            stdio_config=stdio_config,
            description=description,
            tools_enabled=tools_enabled,
            user_id=identity.user_id,
        )

        # Auto-discover and cache tools on creation
        tool_discovery_warning = None
        try:
            mcp_connection_service.discover_tools(created["id"], user_id=identity.user_id)
            # Reload the connection to include cached tools
            created = mcp_connection_service.get_connection(
                created["id"], user_id=identity.user_id
            ) or created
        except Exception as e:
            current_app.logger.error(f"Tool discovery failed on creation: {e}")
            tool_discovery_warning = f"Connection saved but tool discovery failed: {e}"

        resp = {"success": True, "connection": created}
        if tool_discovery_warning:
            resp["warning"] = tool_discovery_warning
        return jsonify(resp), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating MCP connection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/mcp/<connection_id>", methods=["DELETE"])
@require_admin
def delete_mcp_connection(connection_id: str):
    """Delete an MCP connection (owner only)."""
    try:
        identity = get_request_identity()
        ok = mcp_connection_service.delete_connection(connection_id, user_id=identity.user_id)
        if not ok:
            return jsonify({"success": False, "error": "MCP connection not found"}), 404
        return jsonify({"success": True, "message": "MCP connection deleted"}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting MCP connection {connection_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/mcp/<connection_id>/visibility", methods=["PATCH"])
@require_admin
def update_mcp_visibility(connection_id: str):
    """Toggle whether an MCP connection is visible to all users."""
    try:
        data = request.get_json() or {}
        visible_to_all = data.get("visible_to_all")
        if visible_to_all is None:
            return jsonify({"success": False, "error": "visible_to_all is required"}), 400

        updated = mcp_connection_service.update_connection_visibility(
            connection_id, bool(visible_to_all)
        )
        if not updated:
            return jsonify({"success": False, "error": "MCP connection not found"}), 404

        return jsonify({"success": True, "connection": updated}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating MCP visibility {connection_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/mcp/<connection_id>/tools-enabled", methods=["PATCH"])
@require_admin
def update_mcp_tools_enabled(connection_id: str):
    """Toggle whether this connection's tools are available in chat."""
    try:
        data = request.get_json() or {}
        enabled = data.get("tools_enabled")
        if enabled is None:
            return jsonify({"success": False, "error": "tools_enabled is required"}), 400

        updated = mcp_connection_service.update_tools_enabled(connection_id, bool(enabled))
        if not updated:
            return jsonify({"success": False, "error": "MCP connection not found"}), 404

        return jsonify({"success": True, "connection": updated}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating tools_enabled for {connection_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/mcp/validate", methods=["POST"])
@require_admin
def validate_mcp_connection():
    """Validate an MCP connection without saving it."""
    try:
        data = request.get_json() or {}
        transport = (data.get("transport") or "sse").strip()
        server_url = (data.get("server_url") or "").strip()
        auth_type = (data.get("auth_type") or "none").strip()
        auth_config = data.get("auth_config") or {}
        stdio_config = data.get("stdio_config") or {}

        validation = mcp_connection_service.validate_connection(
            transport=transport,
            server_url=server_url,
            auth_type=auth_type,
            auth_config=auth_config,
            stdio_config=stdio_config,
        )
        status_code = 200 if validation.get("valid") else 400
        return jsonify({"success": True, **validation}), status_code
    except Exception as e:
        current_app.logger.error(f"Error validating MCP connection: {e}")
        return jsonify({"success": False, "valid": False, "message": str(e)}), 500


@settings_bp.route("/settings/mcp/<connection_id>/resources", methods=["GET"])
def list_mcp_resources(connection_id: str):
    """List available resources from an MCP server (live call)."""
    try:
        identity = get_request_identity()
        user_id = DEFAULT_USER_ID if not identity.is_authenticated else identity.user_id

        connection = mcp_connection_service.get_connection(
            connection_id=connection_id,
            user_id=user_id,
            include_secret=True,
        )
        if not connection:
            return jsonify({"success": False, "error": "MCP connection not found"}), 404

        from app.services.integrations.mcp.mcp_client import list_resources

        resources = list_resources(
            server_url=connection.get("server_url") or "",
            auth_type=connection.get("auth_type", "none"),
            auth_config=connection.get("auth_config"),
            transport=connection.get("transport", "sse"),
            stdio_config=connection.get("stdio_config"),
        )

        return jsonify({"success": True, "resources": resources, "count": len(resources)}), 200
    except Exception as e:
        current_app.logger.error(f"Error listing MCP resources for {connection_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/mcp/<connection_id>/tools", methods=["GET"])
def list_mcp_tools(connection_id: str):
    """
    Discover tools from an MCP server (live call + cache).

    Educational Note: Makes a real-time call to discover tools, caches them
    in the database, and returns the full tool definitions including input schemas.
    """
    try:
        identity = get_request_identity()
        user_id = DEFAULT_USER_ID if not identity.is_authenticated else identity.user_id

        tools = mcp_connection_service.discover_tools(connection_id, user_id=user_id)
        return jsonify({"success": True, "tools": tools, "count": len(tools)}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error listing MCP tools for {connection_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/mcp/<connection_id>/refresh-tools", methods=["POST"])
@require_admin
def refresh_mcp_tools(connection_id: str):
    """Force refresh cached tool definitions from an MCP server."""
    try:
        identity = get_request_identity()
        tools = mcp_connection_service.discover_tools(connection_id, user_id=identity.user_id)
        return jsonify({"success": True, "tools": tools, "count": len(tools)}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error refreshing MCP tools for {connection_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
