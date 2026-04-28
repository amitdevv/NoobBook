"""
Chunked upload endpoints for large files.

Why chunked?
------------
The classic ``POST /projects/<id>/sources`` endpoint sends the entire
file as a single multipart body, which has to traverse every layer of
the deployment stack: edge proxy → frontend nginx → Flask. Most edge
proxies (Cloudflare Free at 100 MB, default Traefik configs, some
nginx defaults) cap request body bytes — anything larger 413s before
reaching the app.

Chunked upload sidesteps the cap without requiring any infra-level
config. The browser slices the file into pieces small enough to fit
under any reasonable proxy limit (50 MB default), each chunk is a
separate HTTP POST, and the server reassembles them. Self-hostable on
any deployment without grey-clouding hostnames or upgrading proxy
plans.

Three endpoints
---------------

  1. ``POST /projects/<id>/sources/upload-init``
       Validate filename / extension / permission / total size, mint a
       fresh source_id, prepare a temp directory, return the chunk
       size and source_id.

  2. ``POST /projects/<id>/sources/upload-chunk``  (multipart)
       Receive one chunk, append it to the in-progress temp file at
       the right offset (we accept any chunk order; offset is provided
       by the client). Always idempotent for retries.

  3. ``POST /projects/<id>/sources/upload-complete``
       Verify the assembled file's size matches the declared total,
       upload the final blob to Supabase Storage, create the source
       row, kick off processing, delete the temp file.

State during the upload lives in a single growing file on the backend
container's disk under ``UPLOAD_TEMP_ROOT`` (default ``/tmp/noobbook-uploads``).
The temp file is keyed by ``source_id`` so concurrent uploads from the
same user (or anyone) don't collide. We cap upload-init concurrency
implicitly: each call mints a fresh UUID. Orphans (temp files from
crashed uploads) are cleaned by a periodic sweep — see ``_sweep_stale_uploads``.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
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


# Where in-progress uploads accumulate on disk. Container-local; will
# be empty after a redeploy, which is fine — the browser retries from
# chunk 0 on any failure path.
UPLOAD_TEMP_ROOT = Path(os.getenv("UPLOAD_TEMP_ROOT", "/tmp/noobbook-uploads"))

# Default chunk size advertised to the client. 75 MiB sits below
# Cloudflare Free's 100 MB body cap with margin for multipart overhead
# (form field boundaries, Content-Disposition headers, etc.) — fewer
# round trips than 50 MiB without risking a 413. Operators on tighter
# proxies (a 25 MB AWS API Gateway, say) can override via env.
DEFAULT_CHUNK_SIZE = int(os.getenv("UPLOAD_CHUNK_SIZE", str(75 * 1024 * 1024)))

# Hard ceiling on a single chunk we'll accept. Anything larger is
# almost certainly a confused client and would defeat the whole point
# of chunking.
MAX_CHUNK_SIZE = 90 * 1024 * 1024

# Stale uploads (temp files older than this) are reaped on each
# init call. Long enough that a slow upload of a 1GB file with retries
# isn't reaped mid-flight; short enough that abandoned uploads don't
# pile up.
STALE_UPLOAD_AGE_SECONDS = 6 * 60 * 60  # 6 hours


def _check_extension_permission(filename: str) -> Optional[str]:
    """
    Reuse the per-extension permission check from the multipart endpoint.
    Returns an error message string if denied, ``None`` if allowed.
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


def _temp_path(source_id: str) -> Path:
    """The single growing file we accumulate chunks into."""
    return UPLOAD_TEMP_ROOT / f"{source_id}.part"


def _sweep_stale_uploads() -> None:
    """
    Best-effort cleanup of temp files older than STALE_UPLOAD_AGE_SECONDS.
    Called from upload-init; deliberately silent on errors so a quirky
    filesystem doesn't break uploads.
    """
    try:
        if not UPLOAD_TEMP_ROOT.exists():
            return
        now = time.time()
        cutoff = now - STALE_UPLOAD_AGE_SECONDS
        for entry in UPLOAD_TEMP_ROOT.iterdir():
            try:
                if entry.is_file() and entry.stat().st_mtime < cutoff:
                    entry.unlink()
            except Exception:
                continue
    except Exception as exc:
        logger.debug("upload temp sweep failed (non-fatal): %s", exc)


@sources_bp.route('/projects/<project_id>/sources/upload-init', methods=['POST'])
def chunked_upload_init(project_id: str):
    """
    Step 1 — validate up-front and mint a source_id.

    Body:
      {
        "filename":   "...",   // required, original filename for ext + display
        "file_size":  12345    // optional but recommended; lets us reject too-big
                               //   files before any chunks are sent
      }

    Returns:
      {
        "success":    true,
        "source_id":  "<uuid>",
        "chunk_size": 52428800   // bytes the client should slice into
      }
    """
    try:
        UPLOAD_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        _sweep_stale_uploads()

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

        denied = _check_extension_permission(original_filename)
        if denied:
            return jsonify({"success": False, "error": denied}), 403

        # Optional pre-flight size check — saves the browser N round trips
        # for a file that would be rejected at finalize anyway.
        file_size = data.get("file_size")
        if isinstance(file_size, int) and file_size > 0:
            size_error = validate_file_size(original_filename, file_size)
            if size_error:
                return jsonify({"success": False, "error": size_error}), 400

        source_id = str(uuid.uuid4())
        # Pre-create the temp file so chunk-upload can rely on it
        # existing (and gives us a clean error if the disk is read-only).
        try:
            _temp_path(source_id).touch(exist_ok=False)
        except Exception as exc:
            logger.error("Could not create upload temp file: %s", exc)
            return jsonify({
                "success": False,
                "error": "Server temp storage unavailable. Check backend logs.",
            }), 500

        return jsonify({
            "success": True,
            "source_id": source_id,
            "chunk_size": DEFAULT_CHUNK_SIZE,
        }), 200
    except Exception as exc:
        current_app.logger.error("chunked_upload_init failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@sources_bp.route('/projects/<project_id>/sources/upload-chunk', methods=['POST'])
def chunked_upload_chunk(project_id: str):
    """
    Step 2 — receive one chunk and write it to its offset in the temp file.

    Multipart form:
      chunk:   the binary chunk (file field)
      source_id:    source UUID returned by upload-init
      offset:       byte offset where this chunk belongs (0-based)
      total_size:   declared total file size (for tail validation)

    Idempotent on retries — the same chunk re-uploaded at the same
    offset overwrites cleanly. Order doesn't matter as long as every
    byte in [0, total_size) is eventually covered.
    """
    try:
        source_id = (request.form.get("source_id") or "").strip()
        if not source_id:
            return jsonify({"success": False, "error": "source_id is required"}), 400

        try:
            offset = int(request.form.get("offset", "-1"))
            total_size = int(request.form.get("total_size", "-1"))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "offset / total_size must be integers"}), 400

        if offset < 0 or total_size <= 0:
            return jsonify({"success": False, "error": "offset and total_size are required"}), 400

        chunk_file = request.files.get("chunk")
        if not chunk_file:
            return jsonify({"success": False, "error": "chunk file is required"}), 400

        temp = _temp_path(source_id)
        if not temp.exists():
            return jsonify({
                "success": False,
                "error": "Upload session not found — call upload-init first.",
            }), 404

        # Stream the chunk into the temp file at the right offset. Using
        # `r+b` lets us seek; the file was created empty by init.
        with open(temp, "r+b") as f:
            f.seek(offset)
            shutil.copyfileobj(chunk_file.stream, f)

        # Quick sanity: the chunk we just wrote shouldn't push past the
        # declared total. If it does, the client miscalculated; fail
        # loudly so the bug doesn't hide.
        new_size = temp.stat().st_size
        if new_size > total_size:
            return jsonify({
                "success": False,
                "error": f"Chunk would exceed declared total_size ({new_size} > {total_size}).",
            }), 400

        return jsonify({
            "success": True,
            "received_bytes": new_size,
            "expected_total": total_size,
        }), 200
    except Exception as exc:
        current_app.logger.error("chunked_upload_chunk failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@sources_bp.route('/projects/<project_id>/sources/upload-complete', methods=['POST'])
def chunked_upload_complete(project_id: str):
    """
    Step 3 — verify, upload the assembled blob to Supabase, create the
    source row, kick off processing, clean up.

    Body:
      {
        "source_id":   "<uuid>",
        "filename":    "...",   // original filename
        "name":        "...",   // optional display name
        "description": "...",   // optional
        "mime_type":   "...",   // optional; falls back to ext-detected
        "total_size":  12345    // declared size; must match temp file
      }
    """
    try:
        data = request.get_json(silent=True) or {}
        source_id = (data.get("source_id") or "").strip()
        original_filename = (data.get("filename") or "").strip()

        if not source_id or not original_filename:
            return jsonify({
                "success": False,
                "error": "source_id and filename are required",
            }), 400

        # Re-run extension + permission checks on finalize too — someone
        # could call init with a small allowed file and finalize with a
        # different filename otherwise.
        if not is_allowed_file(original_filename):
            return jsonify({"success": False, "error": "File type not allowed"}), 400
        denied = _check_extension_permission(original_filename)
        if denied:
            return jsonify({"success": False, "error": denied}), 403

        temp = _temp_path(source_id)
        if not temp.exists():
            return jsonify({
                "success": False,
                "error": "Upload session not found or already finalized.",
            }), 404

        actual_size = temp.stat().st_size
        try:
            declared_total = int(data.get("total_size", actual_size))
        except (TypeError, ValueError):
            declared_total = actual_size

        if declared_total <= 0 or declared_total != actual_size:
            return jsonify({
                "success": False,
                "error": (
                    f"Assembled size doesn't match declared total "
                    f"({actual_size} bytes on disk, {declared_total} expected). "
                    "Some chunks failed — please retry the upload."
                ),
            }), 400

        size_error = validate_file_size(original_filename, actual_size)
        if size_error:
            try:
                temp.unlink()
            except Exception:
                pass
            return jsonify({"success": False, "error": size_error}), 400

        ext, category, default_mime = get_file_info(original_filename)
        mime_type = (data.get("mime_type") or default_mime or "application/octet-stream").strip()
        stored_filename = f"{source_id}{ext}"

        # Stream the assembled file into Supabase Storage. Passing the
        # file handle (not bytes) keeps the entire 1GB blob off the
        # Python heap — storage3/httpx streams it over the wire.
        try:
            with open(temp, "rb") as f:
                storage_path = storage_service.upload_raw_file(
                    project_id=project_id,
                    source_id=source_id,
                    filename=stored_filename,
                    file_data=f,
                    content_type=mime_type,
                )
        except Exception as exc:
            logger.error("upload to Supabase failed for %s: %s", source_id, exc)
            return jsonify({
                "success": False,
                "error": (
                    "Could not upload assembled file to Supabase Storage. "
                    f"Underlying error: {exc}"
                ),
            }), 500

        if not storage_path:
            # Surface the underlying Supabase Storage error rather than
            # making the user dig through backend logs. The most common
            # cause for self-hosted setups is FILE_SIZE_LIMIT — by
            # default Supabase Storage rejects > 50 MB unless the
            # storage container has FILE_SIZE_LIMIT raised AND the
            # bucket's per-bucket cap is also raised in Studio.
            underlying = storage_service.get_last_upload_error() or "unknown error"
            hint = ""
            low = underlying.lower()
            if "payload too large" in low or "file size" in low or "413" in low:
                hint = (
                    " — Supabase Storage rejected the file as too large. "
                    "Raise FILE_SIZE_LIMIT on the storage container "
                    "(e.g. 1073741824 for 1 GB) AND the per-bucket cap "
                    "in Supabase Studio → Storage → raw-files bucket."
                )
            return jsonify({
                "success": False,
                "error": f"Supabase Storage upload failed: {underlying}{hint}",
            }), 500

        # Source row + processing kick-off — same shape as the multipart
        # endpoint produces.
        timestamp = datetime.now().isoformat()  # noqa: F841
        source_metadata = {
            "id": source_id,
            "project_id": project_id,
            "name": (data.get("name") or original_filename).strip() or original_filename,
            "description": (data.get("description") or "").strip(),
            "type": category.upper(),
            "status": "uploaded",
            "raw_file_path": storage_path,
            "file_size": actual_size,
            "is_active": False,
            "embedding_info": {
                "original_filename": original_filename,
                "mime_type": mime_type,
                "file_extension": ext,
                "stored_filename": stored_filename,
            },
        }
        source_index_service.add_source_to_index(project_id, source_metadata)

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
            source_service_module.update_source(project_id, source_id, status="processing")
        except Exception as exc:
            logger.error("Failed to submit processing task for source %s: %s", source_id, exc)

        # Cleanup temp file — best-effort, the sweep would catch it later.
        try:
            temp.unlink()
        except Exception as exc:
            logger.warning("Could not delete upload temp file %s: %s", temp, exc)

        from app.services.source_services.source_service import SourceService
        shaped = SourceService()._shape_for_frontend(project_id, source_metadata)
        return jsonify({
            "success": True,
            "source": shaped,
            "message": "Source uploaded successfully",
        }), 201
    except Exception as exc:
        current_app.logger.error("chunked_upload_complete failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@sources_bp.route('/projects/<project_id>/sources/upload-abort', methods=['POST'])
def chunked_upload_abort(project_id: str):
    """
    Cancel an in-progress upload — deletes the temp file. Safe to call
    even if the upload doesn't exist (returns success). Intended for
    the browser's beforeunload / explicit cancel paths so we don't leak
    half-uploaded multi-GB temp files.
    """
    try:
        data = request.get_json(silent=True) or {}
        source_id = (data.get("source_id") or "").strip()
        if not source_id:
            return jsonify({"success": False, "error": "source_id is required"}), 400
        temp = _temp_path(source_id)
        if temp.exists():
            try:
                temp.unlink()
            except Exception as exc:
                logger.warning("Could not delete aborted upload %s: %s", temp, exc)
        return jsonify({"success": True}), 200
    except Exception as exc:
        current_app.logger.error("chunked_upload_abort failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500
