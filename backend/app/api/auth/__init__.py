"""
Auth / identity endpoints.

Educational Note: NoobBook supports multi-user setup with RBAC.
This blueprint provides authentication endpoints and /me for frontend RBAC gating.

Routes:
- POST /auth/signup  - Register new user
- POST /auth/signin  - Sign in with email/password
- POST /auth/signout - Sign out
- GET  /auth/me      - Get current user info with RBAC role
"""

from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from app.api.auth import routes  # noqa: F401
