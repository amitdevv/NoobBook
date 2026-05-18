"""
Per-request context helpers — req_id propagation.

Educational Note: There is no way today to take a frontend "I was logged out at
14:32" report and find the corresponding backend log line. This helper, paired
with the X-Request-Id middleware in `app/api/__init__.py` and the matching
header on the frontend axios client, closes that gap. Every log record gets
stamped with the current request's UUID; structured tracers (AUTH_401_TRACE
etc.) include it in the message body too.
"""
from __future__ import annotations


def get_request_id() -> str:
    """
    Return the current request's correlation ID, or "-" outside request context.

    Safe to call from anywhere — including background ThreadPoolExecutor
    workers that have no Flask request context. In that case "-" is
    returned so the format string still renders cleanly.
    """
    try:
        from flask import g, has_request_context
        if has_request_context():
            return getattr(g, "req_id", "-") or "-"
    except Exception:
        pass
    return "-"
