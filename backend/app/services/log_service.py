"""
Log service — operations on the rotating backend log file.

Both the HTTP `POST /logs/clear` route and the weekly
housekeeping scheduler call into this module so the truncate-and-archive-
delete semantics live in exactly one place. Audit-log emission also lives
here so every clear is traceable regardless of which call site triggered it.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.utils import logger as logger_module

logger = logging.getLogger(__name__)


def clear_logs(initiator: str = "unknown") -> Dict[str, Any]:
    """
    Truncate the active log file and remove rotated archives.

    Returns a dict with `success`, `cleared` (file count), and optionally
    a `message` (for the "no log file present" no-op path).

    `initiator` shows up in the audit log entry — pass the requesting
    user id, "scheduler", "admin:<email>", etc. so a future log review
    can attribute the wipe.
    """
    log_file = logger_module.LOG_FILE
    if log_file is None or not log_file.parent.exists():
        return {"success": True, "cleared": 0, "message": "no log file"}

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
        return {"success": False, "error": str(exc)}

    logger.info("Log files cleared by %s (%d files)", initiator, cleared)
    return {"success": True, "cleared": cleared}
