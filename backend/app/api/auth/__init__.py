"""
Auth API Blueprint.

Educational Note: Handles user authentication (signup, login, logout, session).
Uses Supabase Auth for password hashing, JWT issuance, and token refresh.

Routes:
- POST /auth/signup  - Register new user (requires signup key)
- POST /auth/login   - Sign in with email/password
- POST /auth/logout  - Sign out (invalidate session)
- GET  /auth/me      - Get current user info (requires auth)
- POST /auth/refresh - Refresh access token
"""
from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

from app.api.auth import routes  # noqa: F401, E402
