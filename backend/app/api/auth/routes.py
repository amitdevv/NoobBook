"""
Identity and authentication endpoints.

Routes:
- GET  /auth/me      - return current user's identity + RBAC role
- POST /auth/signup  - Create new user account
- POST /auth/signin  - Sign in with email/password
- POST /auth/signout - Sign out
"""

from flask import jsonify, request

from app.api.auth import auth_bp
from app.services.auth.rbac import get_request_identity, is_auth_required
from app.services.integrations.supabase.auth_service import auth_service


@auth_bp.route("/auth/me", methods=["GET"])
def me():
    """Get current user identity with RBAC role info."""
    identity = get_request_identity()
    return (
        jsonify(
            {
                "success": True,
                "auth_required": is_auth_required(),
                "user": {
                    "id": identity.user_id,
                    "email": identity.email,
                    "role": identity.role,
                    "is_admin": identity.is_admin,
                    "is_authenticated": identity.is_authenticated,
                },
            }
        ),
        200,
    )


@auth_bp.route("/auth/signup", methods=["POST"])
def signup():
    """
    Create a new user account (email/password).
    Returns a session with access_token on success.
    """
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "email and password are required"}), 400

    result = auth_service.sign_up(email=email, password=password)
    if not result.get("success"):
        return jsonify({"success": False, "error": result.get("error", "Sign up failed")}), 400

    return jsonify(result), 200


@auth_bp.route("/auth/signin", methods=["POST"])
def signin():
    """
    Sign in with email/password and return session tokens.
    """
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "email and password are required"}), 400

    result = auth_service.sign_in(email=email, password=password)
    if not result.get("success"):
        return jsonify({"success": False, "error": result.get("error", "Sign in failed")}), 400

    return jsonify(result), 200


@auth_bp.route("/auth/signout", methods=["POST"])
def signout():
    """
    Sign out (client should clear tokens).
    """
    result = auth_service.sign_out()
    if not result.get("success"):
        return jsonify({"success": False, "error": result.get("error", "Sign out failed")}), 400
    return jsonify({"success": True}), 200
