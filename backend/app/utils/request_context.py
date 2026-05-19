"""
Per-request context helpers — req_id propagation.

Educational Note: There is no way today to take a frontend "I was logged out at
14:32" report and find the corresponding backend log line. This helper, paired
with the X-Request-Id middleware in `app/api/__init__.py` and the matching
header on the frontend axios client, closes that gap. Every log record gets
stamped with the current request's UUID; structured tracers (AUTH_401_TRACE
etc.) include it in the message body too.

Background threads (the SSE worker spawned for chat streaming, source-
processing tasks, etc.) leave Flask's request context — their log records
default to req_id="-" unless they explicitly opt into propagation via
`set_worker_req_id()`. The SSE worker in `app/api/messages/routes.py` does
this so that PROXY_DISCONNECT_PERSIST and other main_chat_service trace
lines stay grep-able against the originating frontend request_id.
"""
from __future__ import annotations

import contextvars

# ContextVars are per-thread and per-asyncio-task. The SSE worker thread
# sets this once at the top of `worker()`; every log call from that
# thread (including main_chat_service's PROXY_DISCONNECT_PERSIST) then
# sees the right req_id via `get_request_id()`.
_worker_req_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "noobbook_worker_req_id", default="-"
)


def set_worker_req_id(req_id: str) -> None:
    """Stash a req_id in a thread-local ContextVar.

    Call this from the top of any background worker that wants its log
    lines correlated with the originating HTTP request. The Flask request
    context doesn't cross thread boundaries; this is the explicit opt-in.
    """
    if req_id:
        _worker_req_id.set(req_id)


def get_request_id() -> str:
    """
    Return the current request's correlation ID, or "-" if neither source
    is set.

    Resolution order:
      1. Flask request context (`g.req_id`) — covers normal HTTP handlers.
      2. ContextVar (`_worker_req_id`) — covers background workers that
         called `set_worker_req_id()`.
      3. Literal "-" — covers startup / CLI / un-instrumented threads.

    Safe to call from anywhere; never raises.
    """
    try:
        from flask import g, has_request_context
        if has_request_context():
            rid = getattr(g, "req_id", None)
            if rid:
                return rid
    except Exception:
        pass
    return _worker_req_id.get()
