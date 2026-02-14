"""
Auth Middleware - JWT validation for protected routes.

Educational Note: This middleware validates JWT tokens issued by Supabase Auth.
We keep using the SERVICE_KEY Supabase client for database queries (bypasses RLS),
but validate the user's JWT to extract their user_id. This is simpler than
switching to ANON_KEY and lets the backend act as a trusted server.

Token Validation Cache: We cache successful token validations for 60 seconds
to avoid hitting Supabase Auth on every request. This prevents failures when
many concurrent requests (e.g., loading multiple images) overwhelm the Auth
server. JWTs are already self-validating (signed + expiry), so a short cache
window is safe — even if a token is revoked, the cache expires quickly.

Pattern: Decorator-based auth, similar to Flask-Login but using Supabase JWTs.
"""
import functools
import logging
import time
import threading
from typing import Optional, Dict, Tuple

from flask import request, jsonify, g
from app.services.integrations.supabase import get_supabase

logger = logging.getLogger(__name__)

# ─── Token Validation Cache ─────────────────────────────────────────────────
# Educational Note: Without caching, every API request triggers an HTTP call
# to Supabase Auth (get_user). When a page loads multiple images simultaneously,
# 3+ concurrent get_user calls can overwhelm the Auth server, causing 401s.
# Caching the result for 60 seconds fixes this while staying security-safe.
_token_cache: Dict[str, Tuple[str, float]] = {}  # {token: (user_id, expires_at)}
_TOKEN_CACHE_TTL = 60  # seconds
_cache_lock = threading.Lock()


def _get_cached_user_id(token: str) -> Optional[str]:
    """Check if a token has a valid cached validation result."""
    cached = _token_cache.get(token)
    if cached:
        user_id, expires_at = cached
        if time.time() < expires_at:
            return user_id
        # Expired — remove from cache
        with _cache_lock:
            _token_cache.pop(token, None)
    return None


def _cache_token(token: str, user_id: str) -> None:
    """Cache a successful token validation result."""
    with _cache_lock:
        _token_cache[token] = (user_id, time.time() + _TOKEN_CACHE_TTL)
        # Prevent unbounded growth — evict expired entries when cache gets large
        if len(_token_cache) > 100:
            now = time.time()
            expired = [k for k, (_, exp) in _token_cache.items() if now >= exp]
            for k in expired:
                del _token_cache[k]


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

    Performance: Results are cached for 60 seconds to avoid redundant Auth
    server calls when multiple browser elements (images, videos) load
    simultaneously with the same token.

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
        logger.warning("No auth token found (header=%s, query=%s)", bool(auth_header), bool(request.args.get('token')))
        return None

    # Check cache first — avoids redundant Supabase Auth calls
    cached_user_id = _get_cached_user_id(token)
    if cached_user_id:
        return cached_user_id

    try:
        supabase = get_supabase()
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            logger.warning("Auth get_user returned no user")
            return None

        user_id = str(user_response.user.id)
        _cache_token(token, user_id)
        return user_id
    except Exception as e:
        logger.warning("Token validation failed: %s: %s", type(e).__name__, e)
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
