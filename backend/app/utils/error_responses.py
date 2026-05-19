"""
Typed error → HTTP response mapping.

Most route handlers in the codebase use a broad `except Exception` followed by
`jsonify({"success": False, "error": str(e)}), 500`. That turns every failure
mode — database unreachable, Claude rate-limit, supabase RPC denied — into
the same shape: a 500 with whatever stringification the exception happens to
produce. The frontend then shows "Failed to send message" with no actionable
detail.

This module classifies common exception types and returns a richer triple:
  (HTTP status, user-safe message, internal log message)

so that:
  - The HTTP status reflects what went wrong (502 for upstream, 429 for rate,
    503 for service-state, 500 for genuinely unknown).
  - Frontend toasts can show "Database unreachable — check the connection URI"
    instead of "Failed to X", because the response body carries that string.
  - Internal logs still get the full exception representation for debugging.

USAGE in a route:

    from app.utils.error_responses import error_response

    try:
        do_work()
    except Exception as exc:
        return error_response(exc, default_log="Error doing work")

The broad `except Exception` is preserved on purpose — this is additive, not
a replacement for try/except. We don't want to lose any failure path.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from flask import Response, current_app, jsonify

logger = logging.getLogger(__name__)


# Import the exception types we want to classify, but defensively — if a
# dependency is missing in a particular environment the classifier still
# works for the ones that ARE importable.
try:  # noqa: SIM105
    import psycopg2  # type: ignore
    _PSYCOPG2_OPERATIONAL = psycopg2.OperationalError
except Exception:  # noqa: BLE001
    _PSYCOPG2_OPERATIONAL = None

try:
    from pymysql.err import OperationalError as _PYMYSQL_OPERATIONAL  # type: ignore
except Exception:  # noqa: BLE001
    _PYMYSQL_OPERATIONAL = None

try:
    import anthropic  # type: ignore
    _ANTHROPIC_STATUS_ERROR = getattr(anthropic, "APIStatusError", None)
    _ANTHROPIC_TIMEOUT = getattr(anthropic, "APITimeoutError", None)
    _ANTHROPIC_CONNECTION = getattr(anthropic, "APIConnectionError", None)
    _ANTHROPIC_RATE_LIMIT = getattr(anthropic, "RateLimitError", None)
except Exception:  # noqa: BLE001
    _ANTHROPIC_STATUS_ERROR = None
    _ANTHROPIC_TIMEOUT = None
    _ANTHROPIC_CONNECTION = None
    _ANTHROPIC_RATE_LIMIT = None

try:
    from postgrest.exceptions import APIError as _POSTGREST_API_ERROR  # type: ignore
except Exception:  # noqa: BLE001
    _POSTGREST_API_ERROR = None


def _is_instance_safe(exc: Exception, cls: Optional[type]) -> bool:
    return cls is not None and isinstance(exc, cls)


def classify(exc: Exception) -> Tuple[int, str]:
    """Return `(status_code, user_safe_message)` for the given exception.

    Falls back to (500, "Unexpected server error — see logs") for anything
    not recognised, preserving the historical behaviour.
    """
    # External database connection failures (psycopg2 / pymysql).
    if _is_instance_safe(exc, _PSYCOPG2_OPERATIONAL) or _is_instance_safe(exc, _PYMYSQL_OPERATIONAL):
        return 502, "Database unreachable — check the connection URI, host, port, and firewall."

    # Anthropic API issues. RateLimitError extends APIStatusError so it must
    # be checked first.
    if _is_instance_safe(exc, _ANTHROPIC_RATE_LIMIT):
        return 429, "Claude rate limit reached — please retry in a moment."
    if _is_instance_safe(exc, _ANTHROPIC_TIMEOUT) or _is_instance_safe(exc, _ANTHROPIC_CONNECTION):
        return 502, "Claude API temporarily unavailable — please retry."
    if _is_instance_safe(exc, _ANTHROPIC_STATUS_ERROR):
        status = getattr(exc, "status_code", 502) or 502
        if 500 <= status < 600:
            return 502, "Claude API returned a server error — please retry."
        # 4xx from Anthropic is usually our fault (bad request shape), but
        # surface it as 502 to avoid leaking internals to the user.
        return 502, "Claude API rejected the request — please retry or contact support."

    # Postgrest auth/permission errors — most notably the 42501 that the
    # supabase-py listener-pollution bug surfaces post-restart-required.
    if _is_instance_safe(exc, _POSTGREST_API_ERROR):
        code = getattr(exc, "code", None) or ""
        if code == "42501":
            return 503, (
                "A backend service auth state needs reset. "
                "Please contact your admin to restart the server."
            )
        return 502, "Database service returned an error — please retry."

    return 500, "Unexpected server error — see logs."


def error_response(
    exc: Exception,
    *,
    default_log: str = "Unhandled exception",
    extra: Optional[dict[str, Any]] = None,
) -> Tuple[Response, int]:
    """Build a Flask response from a classified exception.

    The internal log line includes the full exception (type + str + stack)
    so debugging isn't degraded. The response body carries only the
    user-safe message.
    """
    status, user_message = classify(exc)
    # Use current_app.logger so the route's normal logging configuration
    # (handlers, filters, formatters with req_id) is honoured.
    try:
        current_app.logger.exception("%s: %s: %s", default_log, type(exc).__name__, exc)
    except RuntimeError:
        # Outside an app context — extremely unlikely from a route, but
        # don't lose the trace if it happens (e.g. background-thread caller
        # using this helper).
        logger.exception("%s: %s: %s", default_log, type(exc).__name__, exc)

    body: dict[str, Any] = {"success": False, "error": user_message}
    if extra:
        body.update(extra)
    return jsonify(body), status
