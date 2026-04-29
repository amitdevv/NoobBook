"""
Editor blueprint — AI-assist + image upload.

Routes:
  POST /editor/assist                    inline AI rewrite (Haiku)
  POST /editor/<project_id>/images       upload an inline image asset

Both are workspace-level affordances on the document editor; the
image route is project-scoped because images live in the project's
storage prefix.
"""
import logging
import uuid

from flask import Blueprint, request, jsonify, current_app, g

from app.config import prompt_loader
from app.services.integrations.claude import claude_service
from app.services.integrations.supabase import storage_service
from app.utils import claude_parsing_utils

logger = logging.getLogger(__name__)

editor_assist_bp = Blueprint("editor_assist", __name__)

# Editor-image constraints
_IMAGE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_IMAGE_ALLOWED = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Action vocabulary mirrored on the frontend. Anything outside this
# set rejects with 400 — keeps prompt-injection surface small.
_ACTIONS = {
    "improve": "improved",
    "continue": "continued",
    "summarize": "summarized",
}


@editor_assist_bp.route("/editor/assist", methods=["POST"])
def editor_assist():
    # Caller is already JWT-validated by api_bp.before_request, but
    # we still want a user_id for cost attribution + Opik tagging.
    try:
        data = request.get_json() or {}
        action = (data.get("action") or "").strip().lower()
        text = (data.get("text") or "").strip()

        if action not in _ACTIONS:
            return jsonify({
                "success": False,
                "error": f"action must be one of {list(_ACTIONS.keys())}",
            }), 400

        if not text:
            return jsonify({
                "success": False,
                "error": "text is required",
            }), 400

        # Lightly cap input. Haiku has a 200K context but the editor
        # only ever sends short selections; anything beyond ~16K chars
        # is almost certainly a misuse and would burn tokens.
        if len(text) > 16_000:
            return jsonify({
                "success": False,
                "error": "Selection too large for inline assist (16k char cap)",
            }), 400

        prompt_config = prompt_loader.get_prompt_config("editor_assist")
        # str.format treats `{...}` as a placeholder, so any user
        # selection containing curly braces (JSON snippets, code,
        # f-strings, Jinja, TS generics, ...) would raise KeyError /
        # IndexError before reaching Claude. Escape the user-controlled
        # value by doubling its braces, which str.format renders back
        # as literal single braces.
        escaped_text = text.replace("{", "{{").replace("}", "}}")
        user_message = prompt_config["user_message"].format(
            action=action,
            action_short=_ACTIONS[action],
            text=escaped_text,
        )

        user_id = getattr(g, "user_id", None)

        response = claude_service.send_message(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=prompt_config["system_prompt"],
            model=prompt_config["model"],
            max_tokens=prompt_config["max_tokens"],
            temperature=prompt_config["temperature"],
            user_id=user_id,
            tags=["editor-assist", f"editor-assist:{action}"],
        )

        result = claude_parsing_utils.extract_text(response).strip()
        if not result:
            return jsonify({
                "success": False,
                "error": "Model returned an empty response",
            }), 502

        return jsonify({"success": True, "result": result, "action": action}), 200

    except Exception as e:
        current_app.logger.error(f"editor_assist failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@editor_assist_bp.route("/editor/<project_id>/images", methods=["POST"])
def upload_editor_image(project_id: str):
    """
    Upload an image dropped/pasted into the document editor. Returns
    a signed URL the editor can insert as a markdown image.

    Multipart: field name `file`. Validates MIME + 10 MB cap.

    Auth: the request must be authenticated (handled by the api_bp
    before_request hook) AND the requesting user must own the
    project. We enforce ownership explicitly here because the backend
    Supabase client uses the service role and bypasses RLS — without
    this guard, any authenticated user could write into any project's
    `_editor-images/` prefix.
    """
    try:
        # Project ownership gate — must come before any storage write.
        from app.services.data_services import project_service
        user_id = getattr(g, "user_id", None)
        project = project_service.get_project(project_id, user_id=user_id)
        if not project:
            return jsonify({
                "success": False,
                "error": "Project not found or access denied",
            }), 404

        if "file" not in request.files:
            return jsonify({"success": False, "error": "file field required"}), 400
        f = request.files["file"]
        mime = (f.mimetype or "").lower()
        if mime not in _IMAGE_ALLOWED:
            return jsonify({
                "success": False,
                "error": f"Unsupported image type {mime}. Allowed: {sorted(_IMAGE_ALLOWED.keys())}",
            }), 400

        # Size check without slurping the whole stream into memory.
        import os
        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)
        if size > _IMAGE_MAX_BYTES:
            return jsonify({
                "success": False,
                "error": f"Image exceeds {_IMAGE_MAX_BYTES // (1024 * 1024)}MB cap",
            }), 400

        ext = _IMAGE_ALLOWED[mime]
        image_id = str(uuid.uuid4())
        stored_filename = f"{image_id}{ext}"

        path = storage_service.upload_editor_image(
            project_id=project_id,
            image_id=image_id,
            filename=stored_filename,
            file_data=f.stream,
            content_type=mime,
        )
        if not path:
            return jsonify({"success": False, "error": "Storage upload failed"}), 500

        signed_url = storage_service.get_editor_image_url(
            project_id=project_id,
            image_id=image_id,
            filename=stored_filename,
        )
        if not signed_url:
            return jsonify({"success": False, "error": "Failed to sign image URL"}), 500

        return jsonify({
            "success": True,
            "url": signed_url,
            "path": path,
            "filename": stored_filename,
        }), 200

    except Exception as e:
        current_app.logger.error(f"editor image upload failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
