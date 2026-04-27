"""
Project Shares — owner-side endpoints (Roadmap #15).

The project owner manages share links here:

* ``GET /projects/<id>/shares`` — list all shares for the project (active,
  expired, revoked) so the UI can render history.
* ``POST /projects/<id>/shares`` — create a new share link.
* ``DELETE /projects/<id>/shares/<share_id>`` — revoke a share.

Viewer-side endpoints live in ``app/api/share/routes.py`` and use a
different auth path (token-based, no JWT requirement for public mode).
"""
import logging
import os
from typing import Optional

from flask import current_app, jsonify, request

from app.api.projects import projects_bp
from app.services.auth.rbac import get_request_identity
from app.services.data_services import project_service, share_service

logger = logging.getLogger(__name__)


# Allowed values for the user-facing expiry selector. None means never expires.
_ALLOWED_EXPIRY_DAYS = {7, 30}


def _build_share_url(token: str) -> str:
    """
    Build the full URL a viewer should open.

    Tries ``PUBLIC_APP_URL`` first (set in env when the deployed origin
    differs from request.host_url, e.g. behind a reverse proxy). Falls
    back to the current request host so dev still works without env config.
    """
    base = (os.getenv("PUBLIC_APP_URL") or "").strip().rstrip("/")
    if not base:
        # Strip trailing slash from host_url for clean concat.
        base = request.host_url.rstrip("/")
    return f"{base}/share/{token}"


def _serialize_share(row: dict) -> dict:
    """Shape a project_shares row for the frontend.

    The ``url`` field is built lazily so we don't store deployment-host
    info in the DB."""
    return {
        "id": row.get("id"),
        "project_id": row.get("project_id"),
        "token": row.get("token"),
        "url": _build_share_url(row.get("token", "")),
        "mode": row.get("mode"),
        "invited_emails": row.get("invited_emails") or [],
        "created_by": row.get("created_by"),
        "created_at": row.get("created_at"),
        "expires_at": row.get("expires_at"),
        "revoked_at": row.get("revoked_at"),
        "is_active": share_service.is_share_usable(row),
    }


@projects_bp.route('/projects/<project_id>/shares', methods=['GET'])
def list_project_shares(project_id: str):
    """List all share links for a project (most recent first)."""
    try:
        identity = get_request_identity()
        # Ownership check — get_project filters by user_id and returns None
        # for non-owners, which we surface as 404 (don't leak existence).
        project = project_service.get_project(project_id, user_id=identity.user_id)
        if not project:
            return jsonify({"success": False, "error": "Project not found"}), 404

        rows = share_service.list_shares_for_project(project_id)
        return jsonify({
            "success": True,
            "shares": [_serialize_share(row) for row in rows],
        }), 200
    except Exception as e:
        current_app.logger.error("Failed to list shares for project %s: %s", project_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route('/projects/<project_id>/shares', methods=['POST'])
def create_project_share(project_id: str):
    """
    Create a new share link.

    Body:
        {
          "mode": "public" | "invited",
          "invited_emails": ["alice@example.com", ...],   // required for invited
          "expires_in_days": 7 | 30 | null                // null = never
        }
    """
    try:
        identity = get_request_identity()
        project = project_service.get_project(project_id, user_id=identity.user_id)
        if not project:
            return jsonify({"success": False, "error": "Project not found"}), 404

        data = request.get_json(silent=True) or {}
        mode = (data.get("mode") or "").strip().lower()
        if mode not in share_service.VALID_MODES:
            return jsonify({
                "success": False,
                "error": f"mode must be one of {sorted(share_service.VALID_MODES)}",
            }), 400

        invited_emails = data.get("invited_emails") or []
        if mode == "invited" and not isinstance(invited_emails, list):
            return jsonify({
                "success": False,
                "error": "invited_emails must be a list of strings",
            }), 400

        expires_in_days_raw = data.get("expires_in_days")
        expires_in_days: Optional[int]
        if expires_in_days_raw is None or expires_in_days_raw == "never":
            expires_in_days = None
        else:
            try:
                expires_in_days = int(expires_in_days_raw)
            except (TypeError, ValueError):
                return jsonify({
                    "success": False,
                    "error": "expires_in_days must be an integer or null",
                }), 400
            if expires_in_days not in _ALLOWED_EXPIRY_DAYS:
                return jsonify({
                    "success": False,
                    "error": f"expires_in_days must be one of {sorted(_ALLOWED_EXPIRY_DAYS)} or null",
                }), 400

        try:
            row = share_service.create_share(
                project_id=project_id,
                created_by=identity.user_id,
                mode=mode,
                invited_emails=invited_emails,
                expires_in_days=expires_in_days,
            )
        except ValueError as ve:
            return jsonify({"success": False, "error": str(ve)}), 400

        return jsonify({
            "success": True,
            "share": _serialize_share(row),
        }), 201
    except Exception as e:
        current_app.logger.error("Failed to create share for project %s: %s", project_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route('/projects/<project_id>/shares/<share_id>', methods=['DELETE'])
def revoke_project_share(project_id: str, share_id: str):
    """Revoke a share. Returns 404 if the share doesn't belong to this project."""
    try:
        identity = get_request_identity()
        project = project_service.get_project(project_id, user_id=identity.user_id)
        if not project:
            return jsonify({"success": False, "error": "Project not found"}), 404

        ok = share_service.revoke_share(share_id, project_id)
        if not ok:
            return jsonify({"success": False, "error": "Share not found"}), 404

        return jsonify({"success": True}), 200
    except Exception as e:
        current_app.logger.error("Failed to revoke share %s: %s", share_id, e)
        return jsonify({"success": False, "error": str(e)}), 500
