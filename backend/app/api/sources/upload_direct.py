"""
Direct-to-Supabase upload endpoints.

The classic ``POST /projects/<id>/sources`` endpoint streams the entire
file body through nginx and Flask before reaching Supabase Storage,
which means anything past Cloudflare's 100 MB body cap (or the user's
edge proxy limit) 413s before we even see it. These two endpoints
flip the flow so the file never traverses our edge / app layer:

  1. ``POST /projects/<id>/sources/upload-init`` validates the request
     and mints a short-lived signed upload URL pointing directly at
     Supabase Storage's public hostname.
  2. The browser PUTs the file body to that URL — Cloudflare and Flask
     are out of the path.
  3. ``POST /projects/<id>/sources/upload-finalize`` confirms the file
     landed, creates the ``sources`` row, and kicks off processing.

Step 3 is a tiny JSON request, so the round-trip back through our edge
proxy is fine. The actual file bytes go to a different hostname (the
public Supabase URL), which is *not* behind the same Cloudflare zone in
typical Coolify deployments.

Per-extension permission checks happen at step 1 — same rules as the
multipart endpoint in ``routes.py``. If any of these checks reject, no
signed URL is returned and the browser never wastes bandwidth.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from flask import current_app, jsonify, request

from app.api.sources import sources_bp
from app.api.sources.routes import _EXT_PERMISSION_MAP
from app.services.auth.permissions import user_has_permission
from app.services.auth.rbac import get_request_identity
from app.services.background_services import task_service
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service
from app.utils.file_utils import (
    ALLOWED_EXTENSIONS,
    get_file_info,
    is_allowed_file,
    validate_file_size,
)

logger = logging.getLogger(__name__)


def _check_extension_permission(filename: str) -> Optional[str]:
    """
    Run the same per-extension permission check used by the multipart
    upload endpoint. Returns an error message (string) if denied, None
    if allowed. Centralized so the init / finalize / multipart paths
    can't drift.
    """
    ext = Path(filename).suffix.lower()
    perm = _EXT_PERMISSION_MAP.get(ext)
    if not perm:
        return None
    identity = get_request_identity()
    if identity.is_admin:
        return None
    if user_has_permission(identity.user_id, perm[0], perm[1]):
        return None
    return "This file type is not available for your account. Contact your admin."


@sources_bp.route('/projects/<project_id>/sources/upload-init', methods=['POST'])
def upload_init(project_id: str):
    """
    Step 1 of the direct-upload flow.

    Body:
      {
        "filename":      "...",   // original filename, used for ext + display
        "content_type":  "...",   // optional; defaults to detected mime
        "file_size":     12345    // optional; if present we run the size check
                                  //   here so the browser doesn't waste an
                                  //   upload that would be rejected anyway
      }

    Returns:
      {
        "success": true,
        "source_id": "<uuid>",
        "upload_url": "https://supabase.../object/upload/sign/raw-files/...?token=...",
        "path": "<project_id>/<source_id>/<stored_filename>",
        "stored_filename": "<source_id>.<ext>",
        "mime_type": "..."
      }
    """
    try:
        data = request.get_json(silent=True) or {}
        original_filename = (data.get("filename") or "").strip()
        if not original_filename:
            return jsonify({"success": False, "error": "filename is required"}), 400

        if not is_allowed_file(original_filename):
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS.keys()))
            return jsonify({
                "success": False,
                "error": f"File type not allowed. Allowed types: {allowed}",
            }), 400

        # Permission check (mirrors routes.py:upload_source).
        denied = _check_extension_permission(original_filename)
        if denied:
            return jsonify({"success": False, "error": denied}), 403

        # Optional pre-upload size check — saves the browser the trip.
        file_size = data.get("file_size")
        if isinstance(file_size, int) and file_size > 0:
            size_error = validate_file_size(original_filename, file_size)
            if size_error:
                return jsonify({"success": False, "error": size_error}), 400

        ext, _category, default_mime = get_file_info(original_filename)
        content_type = (data.get("content_type") or default_mime or "application/octet-stream").strip()

        source_id = str(uuid.uuid4())
        stored_filename = f"{source_id}{ext}"

        signed = storage_service.create_signed_upload_url(
            project_id=project_id,
            source_id=source_id,
            filename=stored_filename,
        )
        if not signed:
            return jsonify({
                "success": False,
                "error": (
                    "Could not create upload URL. Verify Supabase Storage is "
                    "reachable and the raw-files bucket exists."
                ),
            }), 500

        return jsonify({
            "success": True,
            "source_id": source_id,
            "upload_url": signed["upload_url"],
            "path": signed["path"],
            "stored_filename": stored_filename,
            "mime_type": content_type,
        }), 200
    except Exception as exc:
        current_app.logger.error("upload_init failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@sources_bp.route('/projects/<project_id>/sources/upload-finalize', methods=['POST'])
def upload_finalize(project_id: str):
    """
    Step 3 of the direct-upload flow.

    Body:
      {
        "source_id":         "<uuid from upload-init>",
        "filename":          "...",   // original filename for display
        "stored_filename":   "...",   // from upload-init response
        "mime_type":         "...",
        "file_size":         12345,
        "name":              "...",   // optional display name
        "description":       "..."    // optional
      }

    We confirm the file actually exists in storage before creating the
    source row — prevents an attacker from finalizing a row they never
    uploaded for, and surfaces silent client-side failures cleanly.
    """
    try:
        data = request.get_json(silent=True) or {}
        source_id = (data.get("source_id") or "").strip()
        original_filename = (data.get("filename") or "").strip()
        stored_filename = (data.get("stored_filename") or "").strip()
        mime_type = (data.get("mime_type") or "application/octet-stream").strip()
        file_size_raw = data.get("file_size")

        if not source_id or not original_filename or not stored_filename:
            return jsonify({
                "success": False,
                "error": "source_id, filename, and stored_filename are required",
            }), 400

        # Re-run the extension allow-list + permission check on finalize too;
        # someone could call init with an allowed extension and finalize with a
        # different filename otherwise.
        if not is_allowed_file(original_filename):
            return jsonify({"success": False, "error": "File type not allowed"}), 400
        denied = _check_extension_permission(original_filename)
        if denied:
            return jsonify({"success": False, "error": denied}), 403

        try:
            file_size = int(file_size_raw) if file_size_raw is not None else 0
        except (TypeError, ValueError):
            file_size = 0
        if file_size:
            size_error = validate_file_size(original_filename, file_size)
            if size_error:
                return jsonify({"success": False, "error": size_error}), 400

        # Verify the upload landed. This is the integrity check that
        # makes the whole flow safe — without it, finalize is a free
        # source-row insert with no proof the file exists.
        if not storage_service.raw_object_exists(project_id, source_id, stored_filename):
            return jsonify({
                "success": False,
                "error": (
                    "Upload not found in storage. The browser PUT may have "
                    "failed silently — try again, and check the network tab "
                    "for a non-200 response from the Supabase upload URL."
                ),
            }), 400

        ext, category, _detected_mime = get_file_info(original_filename)

        storage_path = f"{project_id}/{source_id}/{stored_filename}"
        timestamp = datetime.now().isoformat()  # noqa: F841 — kept for parity / future use

        source_metadata = {
            "id": source_id,
            "project_id": project_id,
            "name": (data.get("name") or original_filename).strip() or original_filename,
            "description": (data.get("description") or "").strip(),
            "type": category.upper(),  # PDF, IMAGE, AUDIO, etc.
            "status": "uploaded",
            "raw_file_path": storage_path,
            "file_size": file_size,
            "is_active": False,
            "embedding_info": {
                "original_filename": original_filename,
                "mime_type": mime_type,
                "file_extension": ext,
                "stored_filename": stored_filename,
            },
        }

        source_index_service.add_source_to_index(project_id, source_metadata)

        # Kick off background processing — same path the multipart upload uses.
        from app.services.source_services.source_processing import source_processing_service
        from app.services.source_services import source_service as source_service_module

        try:
            task_service.submit_task(
                "source_processing",
                source_id,
                source_processing_service.process_source,
                project_id,
                source_id,
            )
            source_service_module.update_source(
                project_id, source_id, status="processing",
            )
        except Exception as exc:
            logger.error("Failed to submit processing task for source %s: %s", source_id, exc)

        # Shape the response identically to the multipart endpoint so the
        # frontend can swap call sites without touching downstream code.
        from app.services.source_services.source_service import SourceService
        shaped = SourceService()._shape_for_frontend(project_id, source_metadata)
        return jsonify({
            "success": True,
            "source": shaped,
            "message": "Source uploaded successfully",
        }), 201
    except Exception as exc:
        current_app.logger.error("upload_finalize failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500
