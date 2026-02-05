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
from app.services.data_services.user_service import user_service


@settings_bp.route("/settings/users", methods=["GET"])
@require_admin
def list_users():
    try:
        users = user_service.list_users()
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

        user, password = user_service.create_user(email, role)

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
        user_service.delete_user(user_id, identity.user_id)
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

        updated = user_service.update_role(user_id, role)
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
        password = user_service.reset_password(user_id)
        return jsonify({
            "success": True,
            "password": password
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error resetting password: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

