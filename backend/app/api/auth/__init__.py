"""
Auth / identity endpoints.

Educational Note: NoobBook is moving toward a multi-user setup.
This blueprint provides a minimal /me endpoint for frontend RBAC gating.
"""

from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from app.api.auth import routes  # noqa: F401

