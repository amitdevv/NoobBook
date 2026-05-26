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
    """Top-level metadata returned to the viewer when they open the link.

    For project-wide shares (``ctx.chat_id is None``) the chat list
    contains every chat in the project. For chat-scoped shares we look
    up only the one chat and return a list with that single entry —
    the viewer can't see any other chat in the project, even if they
    know its id (see ``get_share_chat`` for the per-fetch guard).
    """
    project = project_service.get_project(ctx.project_id, user_id=ctx.owner_user_id)

    chats: list = []
    if ctx.chat_id:
        # Chat-scoped share: surface only the bookmarked chat. If it
        # was deleted between share-creation and the viewer opening the
        # link, the FK ON DELETE CASCADE should have already removed
        # the row — but stay defensive (list endpoint vs FK timing).
        only_chat = chat_service.get_chat(ctx.project_id, ctx.chat_id)
        if only_chat:
            # list_chats returns metadata-shaped dicts (no messages).
            # Mirror that shape so the frontend can render the rail
            # uniformly. Drop any heavy fields that get_chat eagerly
            # loaded (messages, studio_signals) — the rail just needs
            # id/title/timestamps.
            chats = [{
                "id": only_chat.get("id"),
                "title": only_chat.get("title"),
                "created_at": only_chat.get("created_at"),
                "updated_at": only_chat.get("updated_at"),
                "message_count": only_chat.get("message_count"),
            }]
    else:
        chats = chat_service.list_chats(ctx.project_id)

    return {
        "share": {
            "project_id": ctx.project_id,
            "mode": ctx.mode,
            "url": f"{_public_app_url()}/share/{request.view_args.get('token', '')}",
            "chat_id": ctx.chat_id,
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


def _chat_in_scope(ctx, chat_id: str) -> bool:
    """True if ``chat_id`` is reachable through this share.

    For project-wide shares any chat in the project is in scope. For
    chat-scoped shares only the bookmarked chat is — every other
    chat_id must 404. Path-parameter chat_ids reach this check after
    the decorator has already authorized the project scope, so the
    surface for cross-project traversal is closed.
    """
    if ctx.chat_id is None:
        return True
    return ctx.chat_id == chat_id


def _studio_artifact_referenced_by_scoped_chat(
    ctx, job_id: str, filename: str,
) -> bool:
    """Whether the requested studio artifact is referenced by the
    chat-scoped share's chat.

    Studio outputs live at ``{project_id}/{kind}/{job_id}/{filename}``
    and are linked back to chats through markers in message content
    (e.g. ``[[image:FILENAME]]``, audio/video signal references). The
    schema doesn't store an explicit ``chat_id`` on each artifact, so
    we authorize by content reference: if either the unique ``job_id``
    or the ``filename`` appears anywhere in the scoped chat's messages,
    the viewer reached it through legitimate channels and we allow it.
    Anything else 404s — closing the gap where a holder of a chat-scoped
    token could probe sibling chats' artifacts by guessing UUIDs.

    Best-effort: on lookup failure we deny (return False) rather than
    fail-open, since the worst case is a missing image in a rare race
    against a freshly-created chat.
    """
    try:
        chat = chat_service.get_chat(ctx.project_id, ctx.chat_id)
    except Exception:
        return False
    if not chat:
        return False
    messages = chat.get("messages") or []
    # job_id is a UUID, filename is also generally unique — checking
    # both with substring containment avoids needing to know every
    # studio marker format (image/audio/video/pdf each use their own).
    needles = [n for n in (job_id, filename) if n]
    for msg in messages:
        content = msg.get("content")
        # Content can be a str, a list of typed blocks, or a dict with
        # a `text` field — normalize all to a single string for the
        # substring scan. We accept any text-containing block; image
        # blocks have no payload that would reference another artifact.
        text_parts: list = []
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    txt = block.get("text")
                    if isinstance(txt, str):
                        text_parts.append(txt)
        elif isinstance(content, dict):
            txt = content.get("text")
            if isinstance(txt, str):
                text_parts.append(txt)
        haystack = "\n".join(text_parts)
        if not haystack:
            continue
        for needle in needles:
            if needle in haystack:
                return True
    return False


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
        # Out-of-scope guard for chat-scoped shares. We 404 (not 403)
        # to match the "chat not found" shape the frontend already
        # handles, and to avoid leaking which chat ids exist in the
        # project to a viewer who shouldn't see the list at all.
        if not _chat_in_scope(ctx, chat_id):
            return jsonify({"success": False, "error": "Chat not found"}), 404
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
        # Same scope check as get_share_chat — a chat-scoped share
        # can't be used to resolve citations against chats that aren't
        # in scope, even though chunks themselves are project-scoped.
        if not _chat_in_scope(ctx, chat_id):
            return jsonify({"success": False, "error": "Chat not found"}), 404
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
        # Chat-scoped shares: prevent fetching artifacts that the
        # scoped chat doesn't reference. The path encodes only
        # kind/job_id/filename — no explicit chat_id on the artifact
        # itself — so we authorize by content reference instead.
        # Project-wide shares skip this and remain project-scoped (as
        # before).
        if ctx.chat_id and not _studio_artifact_referenced_by_scoped_chat(
            ctx, job_id, filename,
        ):
            return jsonify({"success": False, "error": "File not found"}), 404
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
    Clone the shared project into the viewer's workspace.

    The fork includes sources, chunks, Pinecone vectors, and every chat
    + messages — see ``project_fork_service`` for the precise scope.
    Returns the new project id and the cloned counterpart of the chat
    the viewer was reading so the frontend can deep-link straight to it.
    """
    try:
        ctx = get_share_context()
        if not ctx.viewer_user_id:
            # Decorator guarantees this with require_jwt=True, but stay defensive.
            return jsonify({"success": False, "error": "Sign in required"}), 401

        # Out-of-scope chat ids 404 the same as any other route. Stops
        # a viewer with a chat-scoped link from forking a sibling chat.
        if not _chat_in_scope(ctx, chat_id):
            return jsonify({"success": False, "error": "Chat not found"}), 404

        # Confirm the chat exists under the share's project before kicking
        # off a multi-second clone. The decorator already authorized
        # access to the project; we just want a clean 404 if the chat id
        # is wrong (e.g. stale link).
        source_chat = chat_service.get_chat(ctx.project_id, chat_id)
        if not source_chat:
            return jsonify({"success": False, "error": "Chat not found"}), 404

        from app.services.data_services.project_fork_service import fork_project

        result = fork_project(
            source_project_id=ctx.project_id,
            source_owner_user_id=ctx.owner_user_id,
            target_user_id=ctx.viewer_user_id,
            seed_chat_id=chat_id,
            # Chat-scoped shares clone only the one chat. Sources +
            # chunks + Pinecone vectors still cloned in full so the
            # cloned chat's citations resolve cleanly.
            chat_only_id=ctx.chat_id,
        )
        if not result:
            return jsonify({"success": False, "error": "Fork failed"}), 500

        return jsonify({
            "success": True,
            "project": {
                "id": result["project_id"],
                "name": result["project_name"],
            },
            # Keep the legacy `chat` shape so the frontend's existing
            # parser doesn't have to change as much.
            "chat": {
                "id": result.get("chat_id"),
                "project_id": result["project_id"],
            } if result.get("chat_id") else None,
            "stats": {
                "source_count": result.get("source_count", 0),
                "chat_count": result.get("chat_count", 0),
            },
        }), 201
    except Exception as exc:
        current_app.logger.error("Share fork failed (%s): %s", chat_id, exc)
        return jsonify({"success": False, "error": str(exc)}), 500
