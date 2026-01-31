"""
Auth endpoints for signup, login, logout, and session management.

Educational Note: These endpoints wrap Supabase Auth operations.
Supabase handles password hashing (bcrypt), JWT generation,
and token refresh. We proxy the requests and format responses.

Signup requires a SIGNUP_KEY to prevent unauthorized account creation.
This acts as a simple invite system — share the key with teammates only.
"""
import os

from flask import request, jsonify
from app.api.auth import auth_bp
from app.services.integrations.supabase.auth_service import auth_service
from app.utils.auth_middleware import require_auth, get_current_user_id


# Signup key from environment — required for creating new accounts
SIGNUP_KEY = os.getenv('SIGNUP_KEY', '')


@auth_bp.route('/auth/signup', methods=['POST'])
def signup():
    """
    Register a new user with email, password, and signup key.

    Educational Note: The signup key is a shared secret that prevents
    random users from creating accounts. Think of it as a simple invite code.
    """
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "Request body is required"}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')
    invite_key = data.get('signup_key', '')

    # Validate required fields
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400

    # Validate signup key
    if not SIGNUP_KEY:
        return jsonify({"success": False, "error": "Signup is not configured. Set SIGNUP_KEY in .env"}), 403

    if invite_key != SIGNUP_KEY:
        return jsonify({"success": False, "error": "Invalid signup key"}), 403

    result = auth_service.sign_up(email, password)

    if not result.get('success'):
        return jsonify({"success": False, "error": result.get('error', 'Signup failed')}), 400

    session = result.get('session')
    user = result.get('user')

    # Supabase may require email confirmation (no session returned)
    if not session:
        return jsonify({
            "success": True,
            "message": "Account created successfully.",
            "requires_confirmation": True
        }), 201

    return jsonify({
        "success": True,
        "user": {"id": str(user.id), "email": user.email},
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in,
    }), 201


@auth_bp.route('/auth/login', methods=['POST'])
def login():
    """Sign in with email and password."""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "Request body is required"}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    result = auth_service.sign_in(email, password)

    if not result.get('success'):
        return jsonify({"success": False, "error": "Invalid email or password"}), 401

    session = result.get('session')
    user = result.get('user')

    return jsonify({
        "success": True,
        "user": {"id": str(user.id), "email": user.email},
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in,
    }), 200


@auth_bp.route('/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Sign out the current user."""
    auth_service.sign_out()
    return jsonify({"success": True}), 200


@auth_bp.route('/auth/me', methods=['GET'])
@require_auth
def get_me():
    """Get the current authenticated user's info."""
    user_id = get_current_user_id()

    from app.services.integrations.supabase import get_supabase
    supabase = get_supabase()
    response = supabase.table("users").select("id, email, created_at").eq("id", user_id).execute()

    if not response.data:
        return jsonify({"success": False, "error": "User not found"}), 404

    user = response.data[0]
    return jsonify({"success": True, "user": user}), 200


@auth_bp.route('/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh an expired access token using a refresh token."""
    data = request.get_json()
    refresh_tok = data.get('refresh_token') if data else None

    if not refresh_tok:
        return jsonify({"success": False, "error": "Refresh token is required"}), 400

    from app.services.integrations.supabase import get_supabase
    supabase = get_supabase()

    try:
        response = supabase.auth.refresh_session(refresh_tok)
        session = response.session

        if not session:
            return jsonify({"success": False, "error": "Invalid refresh token"}), 401

        return jsonify({
            "success": True,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_in": session.expires_in,
        }), 200
    except Exception:
        return jsonify({"success": False, "error": "Failed to refresh token"}), 401
