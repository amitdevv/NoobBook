"""
Logs API routes.

Powers the admin "Logs" UI (chat-header button + Settings tab) and accepts
client-side error reports from the frontend so they end up in the same
log stream as backend errors.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from flask import Response, current_app, g, jsonify, request

from app.api.logs import logs_bp
from app.api.logs.bundle import build_bundle
from app.api.logs.redaction import redact_line
from app.services.auth.rbac import require_admin, require_auth
from app.services.data_services.user_service import get_user_service
from app.services.integrations.supabase import get_supabase, is_supabase_enabled
from app.services.log_service import clear_logs as clear_logs_service
from app.utils import logger as logger_module

logger = logging.getLogger(__name__)

# `2026-05-01 10:23:44 [ERROR] app.services.foo: message` — matches the
# format string in setup_logging(). Loose enough to skip continuation
# lines (stack-trace inner lines) which we still want to include verbatim.
_LINE_RE = re.compile(
    r"^(?P<ts>\d{2}:\d{2}:\d{2})\s+"
    r"\[(?P<level>[A-Z]+)\]\s+"
    r"(?P<logger>[\w.\-]+):\s*"
    r"(?P<message>.*)$"
)


def _read_recent_lines(limit: int, levels: set[str]) -> list[dict[str, Any]]:
    """Tail the active log file and return matching structured lines.

    Reads the whole file once — at 5MB max it's quick and avoids the
    seek-from-end gymnastics that need careful handling around line
    boundaries and UTF-8 multibyte chars.
    """
    if not logger_module.LOG_FILE or not logger_module.LOG_FILE.exists():
        return []

    matched: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None

    try:
        with logger_module.LOG_FILE.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                m = _LINE_RE.match(line)
                if m:
                    if pending and pending["level"] in levels:
                        matched.append(pending)
                        if len(matched) > limit * 4:
                            # Trim early to keep memory bounded on large files.
                            matched = matched[-limit:]
                    pending = {
                        "ts": m.group("ts"),
                        "level": m.group("level"),
                        "logger": m.group("logger"),
                        "message": redact_line(m.group("message")),
                    }
                else:
                    # Continuation of the previous structured line (stack trace etc.)
                    if pending is not None:
                        pending["message"] += "\n" + redact_line(line)
            if pending and pending["level"] in levels:
                matched.append(pending)
    except Exception as exc:
        logger.exception("Failed to read log file: %s", exc)
        return []

    return matched[-limit:]


@logs_bp.route("/logs/recent", methods=["GET"])
@require_auth
def get_recent_logs():
    """Return last N error/warning lines as JSON. `?level=all` includes INFO/DEBUG."""
    try:
        limit = int(request.args.get("n", 100))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 1000))

    level_param = (request.args.get("level") or "errors").lower()
    if level_param == "all":
        levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    elif level_param == "warnings":
        levels = {"WARNING", "ERROR", "CRITICAL"}
    else:
        levels = {"ERROR", "CRITICAL"}

    lines = _read_recent_lines(limit, levels)
    return jsonify(
        {
            "success": True,
            "lines": lines,
            "log_file_present": bool(logger_module.LOG_FILE and logger_module.LOG_FILE.exists()),
        }
    ), 200


@logs_bp.route("/logs/bundle", methods=["GET"])
@require_auth
def download_bundle():
    """Return the support bundle as a ZIP attachment."""
    try:
        data, filename = build_bundle()
    except Exception as exc:
        logger.exception("Failed to build support bundle")
        return jsonify({"success": False, "error": str(exc)}), 500

    return Response(
        data,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


@logs_bp.route("/logs/clear", methods=["POST"])
@require_admin
def clear_logs():
    """Truncate the active log file and remove rotated archives.

    Admin-only: read (`/logs/bundle`) and destroy are asymmetric — any
    authenticated user can pull a copy of the logs, but only admins can
    permanently wipe the server-side diagnostic history (which may be
    the only evidence of a crash or security incident affecting other
    users). The audit log records which admin triggered the clear.

    Surfaced to non-admins in the UI via the "Delete logs from server
    after download" checkbox — that path is gated by this same endpoint,
    so the checkbox is a no-op for non-admins (frontend hides it; if
    they bypass the UI, this returns 403).
    """
    initiator = getattr(g, "user_id", None) or "admin"
    result = clear_logs_service(initiator=str(initiator))
    if not result.get("success"):
        return jsonify(result), 500
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# Per-user "auto-delete on download" preference
# ---------------------------------------------------------------------------

_AUTO_DELETE_SETTINGS_KEY = "auto_delete_logs_on_download"


@logs_bp.route("/logs/preferences", methods=["GET"])
@require_auth
def get_log_preferences():
    """Return the current user's log-related preferences.

    Right now only `auto_delete_on_download` — drives the pre-check of the
    "Delete logs from server after download" checkbox in the bundle dialog.
    """
    user_id = getattr(g, "user_id", None)
    if not user_id:
        return jsonify({"success": False, "error": "missing user"}), 401
    if not is_supabase_enabled():
        return jsonify({"success": True, "auto_delete_on_download": False}), 200
    settings = get_user_service().get_user_settings_raw(user_id)
    return jsonify(
        {
            "success": True,
            "auto_delete_on_download": bool(settings.get(_AUTO_DELETE_SETTINGS_KEY, False)),
        }
    ), 200


@logs_bp.route("/logs/preferences", methods=["PUT"])
@require_auth
def update_log_preferences():
    """Persist the user's log-download preferences in users.settings."""
    user_id = getattr(g, "user_id", None)
    if not user_id:
        return jsonify({"success": False, "error": "missing user"}), 401
    payload = request.get_json(silent=True) or {}
    if "auto_delete_on_download" not in payload:
        return jsonify(
            {"success": False, "error": "auto_delete_on_download is required"}
        ), 400
    value = bool(payload.get("auto_delete_on_download"))
    if not is_supabase_enabled():
        # Best-effort no-op in self-hosted setups without Supabase auth.
        return jsonify({"success": True, "auto_delete_on_download": value}), 200
    saved = get_user_service().set_settings_key(
        user_id, _AUTO_DELETE_SETTINGS_KEY, value
    )
    if not saved:
        return jsonify({"success": False, "error": "could not persist preference"}), 500
    return jsonify({"success": True, "auto_delete_on_download": value}), 200


# ---------------------------------------------------------------------------
# Global "auto-clear logs weekly" admin toggle
# ---------------------------------------------------------------------------

_HOUSEKEEPING_DEFAULT = {"weekly_clear_enabled": True, "last_run_at": None}


def _read_housekeeping() -> dict[str, Any]:
    if not is_supabase_enabled():
        return dict(_HOUSEKEEPING_DEFAULT)
    try:
        client = get_supabase()
        resp = (
            client.table("app_settings")
            .select("log_housekeeping")
            .eq("id", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning("Could not read app_settings.log_housekeeping: %s", exc)
        return dict(_HOUSEKEEPING_DEFAULT)
    rows = resp.data or []
    if not rows:
        return dict(_HOUSEKEEPING_DEFAULT)
    return {**_HOUSEKEEPING_DEFAULT, **(rows[0].get("log_housekeeping") or {})}


@logs_bp.route("/logs/housekeeping", methods=["GET"])
@require_auth
def get_log_housekeeping():
    """Return the global weekly-clear configuration.

    Read is open to any authenticated user so non-admin users can still
    see *when* the next auto-clear is due before they download a bundle.
    """
    config = _read_housekeeping()
    return jsonify(
        {
            "success": True,
            "weekly_clear_enabled": bool(config.get("weekly_clear_enabled", True)),
            "last_run_at": config.get("last_run_at"),
        }
    ), 200


@logs_bp.route("/logs/housekeeping", methods=["PUT"])
@require_admin
def update_log_housekeeping():
    """Admin-only toggle of the weekly auto-clear scheduler."""
    if not is_supabase_enabled():
        return jsonify({"success": False, "error": "supabase not configured"}), 503
    payload = request.get_json(silent=True) or {}
    if "weekly_clear_enabled" not in payload:
        return jsonify(
            {"success": False, "error": "weekly_clear_enabled is required"}
        ), 400
    enabled = bool(payload.get("weekly_clear_enabled"))

    config = _read_housekeeping()
    new_value = {**config, "weekly_clear_enabled": enabled}
    try:
        client = get_supabase()
        resp = (
            client.table("app_settings")
            .update({"log_housekeeping": new_value})
            .eq("id", True)
            .execute()
        )
    except Exception as exc:
        logger.exception("Failed to update app_settings.log_housekeeping")
        return jsonify({"success": False, "error": str(exc)}), 500
    if not resp.data:
        return jsonify({"success": False, "error": "no app_settings row"}), 500
    initiator = getattr(g, "user_id", None) or "admin"
    logger.info(
        "Weekly log auto-clear toggled %s by %s",
        "ENABLED" if enabled else "DISABLED",
        initiator,
    )
    return jsonify(
        {
            "success": True,
            "weekly_clear_enabled": enabled,
            "last_run_at": new_value.get("last_run_at"),
        }
    ), 200


@logs_bp.route("/logs/client", methods=["POST"])
@require_auth
def report_client_error():
    """Frontend hook for browser-side errors.

    Authenticated but not admin-gated — any signed-in user reports their
    own browser errors. The error gets written to backend.log via the
    standard logger so it interleaves with server-side events in the
    bundle.

    Note: `api_bp.before_request` already validates the JWT for every
    `/api/v1/*` route that isn't on the auth/health/share allowlist, so
    `@require_auth` here is defense-in-depth — it pins the contract at
    the route level so a future change to `before_request` (e.g. adding
    `/logs/` to the allowlist by accident) can't silently expose this
    write endpoint to anonymous callers.

    Request body:
        {
          "message": "ReferenceError: foo is not defined",
          "stack":   "...",
          "url":     "https://app.example.com/projects/abc",
          "userAgent": "Mozilla/5.0 ...",
          "timestamp": "2026-05-01T10:23:44.123Z"
        }
    """
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip() or "<empty>"
    stack = (payload.get("stack") or "").strip()
    url = (payload.get("url") or "").strip()
    user_agent = (payload.get("userAgent") or "").strip()
    user_id = getattr(g, "user_id", "anonymous")

    # Truncate to keep the log file from being abused as bulk storage.
    # Caps are conservative — a real browser error rarely exceeds these.
    if len(message) > 1000:
        message = message[:1000] + "…(truncated)"
    if len(stack) > 4000:
        stack = stack[:4000] + "\n…(truncated)"
    if len(url) > 500:
        url = url[:500] + "…"
    if len(user_agent) > 200:
        user_agent = user_agent[:200]

    summary = (
        f"[CLIENT user={user_id} url={url} ua={user_agent[:80]}] {message}"
    )
    if stack:
        summary += f"\n{stack}"

    # Use the dedicated frontend-error logger so reviewers can grep [CLIENT]
    # and trace which user / route surfaced the error.
    logging.getLogger("client.error").error(summary)

    # Don't leak whether anything specific happened — keep the response
    # minimal so a malicious script can't probe via response shape.
    return jsonify({"success": True}), 200
