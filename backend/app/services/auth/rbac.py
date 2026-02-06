"""
RBAC (Role-Based Access Control) helpers.

Current scope:
- Two roles: "admin" and "user"
- Admin-only gating for endpoints that expose/change secrets and global config.

Authentication note:
- NoobBook is currently largely single-user (DEFAULT_USER_ID).
- If an Authorization Bearer token is present and Supabase is configured, we try
  to resolve the user via Supabase Auth and load the role from public.users.
- Otherwise we fall back to DEFAULT_USER_ID (admin).
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from flask import jsonify, request

from app.services.integrations.supabase import get_supabase, is_supabase_enabled
from app.services.data_services.project_service import DEFAULT_USER_ID


ROLE_ADMIN = "admin"
ROLE_USER = "user"
_VALID_ROLES = {ROLE_ADMIN, ROLE_USER}

T = TypeVar("T", bound=Callable[..., Any])


@dataclass(frozen=True)
class RequestIdentity:
    user_id: str
    email: Optional[str]
    role: str
    is_authenticated: bool

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


def is_auth_required() -> bool:
    """
    Check if authentication is required for all API routes.

    Controlled via env var NOOBBOOK_AUTH_REQUIRED.
    """
    value = os.getenv("NOOBBOOK_AUTH_REQUIRED", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _get_bearer_token() -> Optional[str]:
    """
    Extract the JWT from the request.

    Checks Authorization header first, then falls back to ?token= query parameter.
    The query param fallback is needed for browser elements like <img>, <video>,
    <audio>, and <iframe> that can't send custom headers.
    """
    auth = request.headers.get("Authorization", "")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip() or None
    # Fallback: check query parameter for browser elements (img, video, etc.)
    return request.args.get("token") or None


def _load_role_from_users_table(user_id: str) -> Optional[str]:
    if not is_supabase_enabled():
        return None
    try:
        supabase = get_supabase()
        resp = supabase.table("users").select("role").eq("id", user_id).execute()
        if resp.data and isinstance(resp.data, list):
            role = (resp.data[0].get("role") or "").strip().lower()
            return role if role in _VALID_ROLES else None
    except Exception:
        return None
    return None


def get_request_identity() -> RequestIdentity:
    """
    Resolve the current request's identity + role.

    Priority:
    1) Supabase Auth JWT (Authorization: Bearer <jwt>) if Supabase configured
    2) Explicit dev headers (X-NoobBook-User-Id / X-NoobBook-Role)
    3) Single-user fallback (DEFAULT_USER_ID as admin)
    """
    # 1) Supabase Auth JWT
    token = _get_bearer_token()
    if token and is_supabase_enabled():
        try:
            supabase = get_supabase()
            # supabase-py supports passing jwt to get_user
            user_resp = supabase.auth.get_user(token)
            user = getattr(user_resp, "user", None) or user_resp
            user_id = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
            email = getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None)
            if user_id:
                role = _load_role_from_users_table(user_id) or ROLE_USER
                return RequestIdentity(
                    user_id=str(user_id),
                    email=str(email) if email else None,
                    role=role,
                    is_authenticated=True,
                )
        except Exception:
            # Fall through to dev/single-user mode
            pass

    # 2) Dev headers (useful until full auth UI is wired)
    header_user_id = (request.headers.get("X-NoobBook-User-Id") or "").strip()
    header_role = (request.headers.get("X-NoobBook-Role") or "").strip().lower()
    if header_user_id:
        role = header_role if header_role in _VALID_ROLES else (_load_role_from_users_table(header_user_id) or ROLE_USER)
        return RequestIdentity(
            user_id=header_user_id,
            email=None,
            role=role,
            is_authenticated=True,
        )

    # 3) Single-user fallback
    auth_required = is_auth_required()
    fallback_role = ROLE_ADMIN if not auth_required else ROLE_USER
    return RequestIdentity(
        user_id=DEFAULT_USER_ID,
        email=None,
        role=fallback_role,
        is_authenticated=False,
    )


def require_admin(fn: T) -> T:
    """Decorator to enforce admin role."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        identity = get_request_identity()
        if is_auth_required() and not identity.is_authenticated:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Authentication required",
                        "required_role": ROLE_ADMIN,
                    }
                ),
                401,
            )
        if not identity.is_admin:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Admin access required",
                        "required_role": ROLE_ADMIN,
                        "role": identity.role,
                    }
                ),
                403,
            )
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_auth(fn: T) -> T:
    """Decorator to enforce authenticated user (any role)."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        if not is_auth_required():
            return fn(*args, **kwargs)

        identity = get_request_identity()
        if not identity.is_authenticated:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Authentication required",
                    }
                ),
                401,
            )
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
