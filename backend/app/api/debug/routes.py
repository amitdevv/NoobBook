"""
Admin-only diagnostic endpoints.

Designed for "is something wrong RIGHT NOW?" checks during a live incident.
Neither route mutates state; both are admin-gated.
"""
from __future__ import annotations

import logging

from flask import jsonify

from app.api.debug import debug_bp
from app.services.auth.rbac import require_admin
from app.services.integrations.supabase import check_singleton_identity

logger = logging.getLogger(__name__)


@debug_bp.route("/debug/supabase-state", methods=["GET"])
@require_admin
def supabase_state():
    """Return the data singleton's current identity (is it polluted?).

    See `check_singleton_identity()` for the why. Useful when a user reports
    a spontaneous logout or 42501-class permission error — one curl confirms
    or rules out the supabase-py 2.15.0 listener-pollution bug.
    """
    state = check_singleton_identity()
    return jsonify({"success": True, **state}), 200


@debug_bp.route("/debug/stats", methods=["GET"])
@require_admin
def runtime_stats():
    """Snapshot of in-process counters useful during an incident.

    Reads existing module-level state without mutating anything:
      - in_flight_chats: number of SSE chat streams currently being served
      - token_cache_size: entries in the auth_middleware revocation cache
      - background_executor: queued/active counts for the source-processing
        ThreadPoolExecutor (best-effort — CPython's executor doesn't expose
        a public queue length, so we report what we can).
    """
    out: dict = {}

    # In-flight chat streams
    try:
        from app.api.messages.routes import _in_flight_chats, _in_flight_lock
        with _in_flight_lock:
            out["in_flight_chats"] = len(_in_flight_chats)
    except Exception as exc:  # noqa: BLE001
        out["in_flight_chats_error"] = f"{type(exc).__name__}: {exc}"

    # Token revocation cache size
    try:
        from app.utils.auth_middleware import _token_cache, _cache_lock
        with _cache_lock:
            out["token_cache_size"] = len(_token_cache)
    except Exception as exc:  # noqa: BLE001
        out["token_cache_size_error"] = f"{type(exc).__name__}: {exc}"

    # Background ThreadPoolExecutor — actively-running futures plus the
    # in-memory cancelled set
    try:
        from app.services.background_services.task_service import task_service
        out["background_active_futures"] = len(task_service._futures)
        out["background_cancelled_set_size"] = len(task_service._cancelled_tasks)
        out["background_max_workers"] = task_service.MAX_WORKERS
    except Exception as exc:  # noqa: BLE001
        out["background_executor_error"] = f"{type(exc).__name__}: {exc}"

    return jsonify({"success": True, "stats": out}), 200
