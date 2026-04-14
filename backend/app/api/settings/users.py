"""
User management endpoints (admin only).

Routes:
- GET  /settings/users
- POST /settings/users
- DELETE /settings/users/<user_id>
- PUT  /settings/users/<user_id>/role
- POST /settings/users/<user_id>/reset-password
"""
from flask import jsonify, request, current_app

from app.api.settings import settings_bp
from app.services.auth.rbac import require_admin, get_request_identity
from app.services.data_services.user_service import get_user_service


@settings_bp.route("/settings/users", methods=["GET"])
@require_admin
def list_users():
    try:
        users = get_user_service().list_users()
        return jsonify({"success": True, "users": users, "count": len(users)}), 200
    except Exception as e:
        current_app.logger.error(f"Error listing users: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/users", methods=["POST"])
@require_admin
def create_user():
    """Create a new user with a generated password."""
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip()
        role = (data.get("role") or "user").strip().lower()

        if not email:
            return jsonify({"success": False, "error": "Email is required"}), 400

        user, password = get_user_service().create_user(email, role)

        return jsonify({
            "success": True,
            "user": user,
            "password": password
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating user: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/users/<user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id: str):
    """Delete a user."""
    try:
        identity = get_request_identity()
        get_user_service().delete_user(user_id, identity.user_id)
        return jsonify({"success": True}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error deleting user: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/users/<user_id>/role", methods=["PUT"])
@require_admin
def update_user_role(user_id: str):
    try:
        data = request.get_json() or {}
        role = (data.get("role") or "").strip().lower()
        if role not in {"admin", "user"}:
            return jsonify({"success": False, "error": "role must be 'admin' or 'user'"}), 400

        updated = get_user_service().update_role(user_id, role)
        if not updated:
            return jsonify({"success": False, "error": "User not found"}), 404

        return jsonify({"success": True, "user": updated}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error updating user role: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/users/<user_id>/reset-password", methods=["POST"])
@require_admin
def reset_user_password(user_id: str):
    """Reset a user's password to a new generated password."""
    try:
        password = get_user_service().reset_password(user_id)
        return jsonify({
            "success": True,
            "password": password
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error resetting password: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/users/<user_id>/permissions", methods=["GET"])
@require_admin
def get_user_permissions_endpoint(user_id: str):
    """
    Get a user's module permissions.

    Educational Note: Returns the full permission structure with all
    5 categories and their sub-items. NULL in the DB is resolved to
    the all-enabled default before returning.
    """
    from app.services.auth.permissions import (
        get_user_permissions, get_all_connections, get_user_connection_access,
    )
    perms = get_user_permissions(user_id)
    connections = get_all_connections()
    user_access = get_user_connection_access(user_id)
    return jsonify({
        "success": True,
        "permissions": perms,
        "connections": connections,
        "connection_access": user_access,
    }), 200


@settings_bp.route("/settings/users/<user_id>/permissions", methods=["PUT"])
@require_admin
def update_user_permissions_endpoint(user_id: str):
    """
    Update a user's module permissions AND per-connection access.

    Educational Note: Accepts the full permissions structure plus optional
    connection_access with database_ids and mcp_ids arrays.
    """
    from app.services.auth.permissions import (
        update_user_permissions, update_user_connection_access,
    )
    data = request.get_json() or {}
    permissions = data.get("permissions")
    if permissions is None:
        return jsonify({"success": False, "error": "permissions field required"}), 400

    success = update_user_permissions(user_id, permissions)
    if not success:
        return jsonify({"success": False, "error": "Failed to update permissions"}), 500

    # Update per-connection access if provided
    conn_access = data.get("connection_access")
    if conn_access:
        update_user_connection_access(
            user_id,
            database_ids=conn_access.get("database_ids"),
            mcp_ids=conn_access.get("mcp_ids"),
        )

    return jsonify({"success": True}), 200


@settings_bp.route("/settings/users/me/permissions", methods=["GET"])
def get_my_permissions():
    """
    Get the current user's module permissions.

    Educational Note: Non-admin endpoint — any authenticated user can
    fetch their own permissions so the frontend knows what to show/hide.
    """
    from app.services.auth.rbac import get_request_identity
    from app.services.auth.permissions import get_user_permissions

    identity = get_request_identity()

    # Admins always get full access
    if identity.is_admin:
        from app.services.auth.permissions import DEFAULT_PERMISSIONS
        return jsonify({"success": True, "permissions": DEFAULT_PERMISSIONS}), 200

    perms = get_user_permissions(identity.user_id)
    return jsonify({"success": True, "permissions": perms}), 200


@settings_bp.route("/settings/users/<user_id>/cost-limit", methods=["PUT"])
@require_admin
def update_cost_limit(user_id: str):
    """
    Set or clear a user's spending limit in USD.

    Body: {"cost_limit": 20.0}  — set limit to $20
    Body: {"cost_limit": null}  — remove limit (unlimited)
    """
    data = request.get_json() or {}
    cost_limit = data.get("cost_limit")

    # Validate
    if cost_limit is not None:
        try:
            cost_limit = float(cost_limit)
            if cost_limit < 0:
                return jsonify({"success": False, "error": "Cost limit must be positive"}), 400
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Invalid cost_limit value"}), 400

    success = get_user_service().update_cost_limit(user_id, cost_limit)
    if not success:
        return jsonify({"success": False, "error": "User not found"}), 404

    return jsonify({"success": True, "cost_limit": cost_limit}), 200

