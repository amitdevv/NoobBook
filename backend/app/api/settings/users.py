"""
User management endpoints (admin only).

Routes:
- GET  /settings/users
- PUT  /settings/users/<user_id>/role
"""
from flask import jsonify, request, current_app

from app.api.settings import settings_bp
from app.services.auth.rbac import require_admin
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

