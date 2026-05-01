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
from app.services.auth.rbac import require_admin
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
@require_admin
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
@require_admin
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

    Useful when the admin wants a clean window before reproducing a bug
    so the bundle they ship contains only the relevant noise.
    """
    log_file = logger_module.LOG_FILE
    if log_file is None or not log_file.parent.exists():
        return jsonify({"success": True, "cleared": 0, "message": "no log file"}), 200

    cleared = 0
    try:
        if log_file.exists():
            log_file.write_text("", encoding="utf-8")
            cleared += 1
        for archive in log_file.parent.glob(f"{log_file.name}.*"):
            try:
                archive.unlink()
                cleared += 1
            except OSError as exc:
                logger.warning("Could not delete archive %s: %s", archive, exc)
    except Exception as exc:
        logger.exception("Failed to clear logs")
        return jsonify({"success": False, "error": str(exc)}), 500

    logger.info("Log files cleared by admin (%d files)", cleared)
    return jsonify({"success": True, "cleared": cleared}), 200


@logs_bp.route("/logs/client", methods=["POST"])
def report_client_error():
    """Frontend hook for browser-side errors.

    Authenticated but not admin-gated — any signed-in user reports their
    own browser errors. The error gets written to backend.log via the
    standard logger so it interleaves with server-side events in the
    bundle.

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
    if len(message) > 1000:
        message = message[:1000] + "…(truncated)"
    if len(stack) > 4000:
        stack = stack[:4000] + "\n…(truncated)"

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
