"""
Auth Middleware - JWT validation for protected routes.

Educational Note: This middleware validates JWT tokens issued by Supabase Auth.
We keep using the SERVICE_KEY Supabase client for database queries (bypasses RLS),
but validate the user's JWT to extract their user_id. This is simpler than
switching to ANON_KEY and lets the backend act as a trusted server.

Pattern: Decorator-based auth, similar to Flask-Login but using Supabase JWTs.
"""
import functools
from typing import Optional

from flask import request, jsonify, g
from app.services.integrations.supabase import get_supabase


def get_current_user_id() -> Optional[str]:
    """
    Get the authenticated user's ID from the request context.

    Must be called within a request that passed JWT validation
    (either via @require_auth or the before_request hook).

    Returns:
        User ID string or None if not authenticated
    """
    return getattr(g, 'user_id', None)


def validate_token() -> Optional[str]:
    """
    Validate the JWT from the Authorization header (or ?token= query param) and return the user_id.

    Returns:
        User ID string on success, None on failure

    Educational Note: We call supabase.auth.get_user(jwt) which contacts
    the Supabase Auth server to verify the token signature and expiration.
    The SERVICE_KEY client has permission to validate any user's token.

    Query param fallback: Browser elements like <img>, <video>, <audio>, and <iframe>
    can't send Authorization headers. For these, the frontend appends ?token=JWT
    to the URL. We only check the query param when no Authorization header is present.
    """
    auth_header = request.headers.get('Authorization', '')

    if auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Strip "Bearer "
    else:
        # Fallback: check query parameter for browser elements (img, video, iframe, etc.)
        token = request.args.get('token', '')

    if not token:
        return None

    try:
        supabase = get_supabase()
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            return None

        return str(user_response.user.id)
    except Exception:
        return None


def verify_project_access(project_id: str) -> Optional[tuple]:
    """
    Verify the current user owns the given project.

    Call at the top of any route that takes a project_id to prevent
    users from accessing other users' data (chats, sources, brand, etc.).

    Returns:
        None if the user owns the project.
        (jsonify error, 404) tuple if not — return this from the route.

    Usage:
        denied = verify_project_access(project_id)
        if denied:
            return denied
    """
    from app.services.data_services import project_service

    user_id = get_current_user_id()
    project = project_service.get_project(project_id, user_id=user_id)

    if not project:
        return jsonify({"success": False, "error": "Project not found"}), 404

    return None


def require_auth(f):
    """
    Decorator that requires a valid Supabase JWT in the Authorization header.

    Sets g.user_id on success. Returns 401 on failure.
    Use this for routes that need explicit auth (e.g., /auth/me, /auth/logout).
    Most routes are protected by the before_request hook in api/__init__.py instead.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = validate_token()

        if not user_id:
            return jsonify({"success": False, "error": "Authentication required"}), 401

        g.user_id = user_id
        return f(*args, **kwargs)

    return decorated
