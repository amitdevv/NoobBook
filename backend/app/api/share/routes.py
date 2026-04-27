"""
Share viewer endpoints (Roadmap #15).

Each route is gated by ``@require_share_token``. The decorator validates
the URL token, checks expiry/revocation, enforces invited-mode email
match, and attaches ``g.share_context`` for the route body.

Owner-side endpoints (create / list / revoke) live in
``app/api/projects/shares.py``.
"""
import logging
import os
from typing import Optional

from flask import current_app, g, jsonify, request, send_file
import io

from app.api.share import share_bp
from app.services.auth.share_token import require_share_token, get_share_context
from app.services.data_services import (
    chat_service,
    message_service,
    project_service,
    share_service,
)
from app.utils.citation_utils import get_chunk_content
from app.services.integrations.supabase import storage_service

logger = logging.getLogger(__name__)


def _public_app_url() -> str:
    """Best-effort public URL — same logic as projects/shares.py."""
    base = (os.getenv("PUBLIC_APP_URL") or "").strip().rstrip("/")
    if not base:
        base = request.host_url.rstrip("/")
    return base


def _share_root_payload(ctx) -> dict:
    """Top-level metadata returned to the viewer when they open the link."""
    project = project_service.get_project(ctx.project_id, user_id=ctx.owner_user_id)
    chats = chat_service.list_chats(ctx.project_id)
    return {
        "share": {
            "project_id": ctx.project_id,
            "mode": ctx.mode,
            "url": f"{_public_app_url()}/share/{request.view_args.get('token', '')}",
        },
        "project": {
            "id": project.get("id") if project else ctx.project_id,
            # Only the public-facing fields. Don't leak custom prompt,
            # API key flags, memory, costs, or settings_overrides.
            "name": (project or {}).get("name") or "Shared project",
            "description": (project or {}).get("description") or "",
        },
        "chats": chats,
        "viewer": {
            "is_authenticated": bool(ctx.viewer_user_id),
            "user_id": ctx.viewer_user_id,
            "email": ctx.viewer_email,
        },
    }


@share_bp.route('/share/<token>', methods=['GET'])
@require_share_token()
def get_share_root(token: str):  # noqa: ARG001 — token is consumed by the decorator
    """Return project metadata + chat list for the share landing page."""
    try:
        ctx = get_share_context()
        return jsonify({"success": True, **_share_root_payload(ctx)}), 200
    except Exception as exc:
        current_app.logger.error("Share root failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@share_bp.route('/share/<token>/chats/<chat_id>', methods=['GET'])
@require_share_token()
def get_share_chat(token: str, chat_id: str):  # noqa: ARG001
    """Full chat — messages, citations, studio_signals, costs."""
    try:
        ctx = get_share_context()
        chat = chat_service.get_chat(ctx.project_id, chat_id)
        if not chat:
            return jsonify({"success": False, "error": "Chat not found"}), 404
        return jsonify({"success": True, "chat": chat}), 200
    except Exception as exc:
        current_app.logger.error("Share chat fetch failed (%s): %s", chat_id, exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@share_bp.route('/share/<token>/chats/<chat_id>/citations/<chunk_id>', methods=['GET'])
@require_share_token()
def get_share_citation(token: str, chat_id: str, chunk_id: str):  # noqa: ARG001
    """
    Citation tooltip content. Scoped to the share's project_id, so a
    viewer can only resolve chunks that live inside the shared project.
    """
    try:
        ctx = get_share_context()
        # Verify the chat itself belongs to this project (guards against
        # crafted chat_ids — chunks are project-scoped but the chat path
        # should still be self-consistent).
        chat = chat_service.get_chat(ctx.project_id, chat_id)
        if not chat:
            return jsonify({"success": False, "error": "Chat not found"}), 404

        chunk_data = get_chunk_content(ctx.project_id, chunk_id)
        if not chunk_data:
            return jsonify({"success": False, "error": f"Chunk not found: {chunk_id}"}), 404

        return jsonify({
            "success": True,
            "chunk": {
                "content": chunk_data["content"],
                "chunk_id": chunk_data["chunk_id"],
                "source_id": chunk_data["source_id"],
                "source_name": chunk_data["source_name"],
                "page_number": chunk_data["page_number"],
                "chunk_index": chunk_data["chunk_index"],
            },
        }), 200
    except Exception as exc:
        current_app.logger.error("Share citation lookup failed (%s): %s", chunk_id, exc)
        return jsonify({"success": False, "error": str(exc)}), 500


# Allowlisted studio job-type segments. Mirrors the values used by
# studio_services / tool_executors when they call
# storage_service.upload_studio_binary(...). Anything outside this set is
# rejected at the route layer so a malformed `kind` can never reach the
# storage path builder, regardless of how that helper evolves.
_ALLOWED_STUDIO_KINDS = frozenset({
    "creatives",         # ad creatives
    "social_posts",      # social media posts
    "infographics",      # infographic images
    "blogs",             # blog post images
    "emails",            # email template assets
    "websites",          # website assets (under /assets/ subpath)
    "audio",             # audio overviews
    "video",             # video overviews
    "presentations",     # presentation decks
    "business_reports",  # business reports
    "prds",              # PRD documents
    "components",        # UI components
    "wireframes",        # wireframe screens
    "mind_maps",         # mind maps
    "flow_diagrams",     # flow diagrams
    "flash_cards",       # flash cards
    "quizzes",           # quizzes
    "marketing_strategies",  # marketing strategy docs
})


@share_bp.route('/share/<token>/studio/<kind>/<job_id>/<path:filename>', methods=['GET'])
@require_share_token()
def get_share_studio_artifact(token: str, kind: str, job_id: str, filename: str):  # noqa: ARG001
    """
    Proxy a studio output file (image, audio, etc.) to the viewer.

    The viewer doesn't have a JWT in public mode, so they can't hit the
    owner-only studio routes directly. We download from Supabase Storage
    here and stream it back. Scoped to the share's project_id — files
    outside the project are unreachable. The `kind` segment is checked
    against an allowlist so the URL can't synthesize unexpected storage
    paths.
    """
    try:
        ctx = get_share_context()
        if kind not in _ALLOWED_STUDIO_KINDS:
            return jsonify({"success": False, "error": "Unknown studio kind"}), 404
        # Walk the Supabase Storage path the studio uploads use.
        # storage_service.upload_studio_binary writes to:
        #   project_id/{kind}/{job_id}/{filename}
        # The download_studio_binary helper reads from the same shape.
        file_data = storage_service.download_studio_binary(
            ctx.project_id, kind, job_id, filename,
        )
        if file_data is None:
            return jsonify({"success": False, "error": "File not found"}), 404

        # Best-effort MIME from extension. Most studio outputs are PNG / MP3.
        ext = (filename.rsplit('.', 1)[-1] or '').lower()
        mime = {
            'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'webp': 'image/webp', 'svg': 'image/svg+xml',
            'mp3': 'audio/mpeg', 'wav': 'audio/wav',
            'mp4': 'video/mp4', 'webm': 'video/webm',
            'pdf': 'application/pdf',
        }.get(ext, 'application/octet-stream')

        return send_file(io.BytesIO(file_data), mimetype=mime, as_attachment=False)
    except Exception as exc:
        current_app.logger.error("Share studio proxy failed (%s/%s/%s): %s", kind, job_id, filename, exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@share_bp.route('/share/<token>/chats/<chat_id>/fork', methods=['POST'])
@require_share_token(require_jwt=True)
def fork_share_chat(token: str, chat_id: str):  # noqa: ARG001
    """
    Copy a shared chat into the viewer's own workspace ("Shared with me"
    auto-project). Returns the new project + chat IDs so the frontend
    can navigate to the viewer's writable copy.
    """
    try:
        ctx = get_share_context()
        if not ctx.viewer_user_id:
            # Decorator guarantees this with require_jwt=True, but stay defensive.
            return jsonify({"success": False, "error": "Sign in required"}), 401

        # Fetch the source chat under the SHARE's project_id (not the
        # viewer's). This is the cross-project read the share grants.
        source_chat = chat_service.get_chat(ctx.project_id, chat_id, include_raw=True)
        if not source_chat:
            return jsonify({"success": False, "error": "Chat not found"}), 404

        target_project = project_service.ensure_shared_with_me_project(ctx.viewer_user_id)
        if not target_project:
            return jsonify({"success": False, "error": "Could not create destination project"}), 500

        new_chat = chat_service.fork_chat(
            source_project_id=ctx.project_id,
            source_chat_id=chat_id,
            target_project_id=target_project["id"],
            target_user_id=ctx.viewer_user_id,
        )
        if not new_chat:
            return jsonify({"success": False, "error": "Fork failed"}), 500

        return jsonify({
            "success": True,
            "project": target_project,
            "chat": new_chat,
        }), 201
    except Exception as exc:
        current_app.logger.error("Share fork failed (%s): %s", chat_id, exc)
        return jsonify({"success": False, "error": str(exc)}), 500
