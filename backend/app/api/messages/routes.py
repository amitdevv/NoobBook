"""
Message endpoints - the core AI interaction.

Educational Note: This is where the magic happens! When a user sends a message,
the main_chat_service orchestrates:

1. Context Building:
   - Loads project sources (with summaries)
   - Loads user and project memory
   - Builds dynamic system prompt

2. Claude API Call:
   - Sends conversation history + context
   - Provides tools: search_sources, store_memory

3. Tool Use Loop (Agentic Pattern):
   - Claude may call search_sources to query embeddings
   - Claude may call store_memory to save important info
   - Loop continues until Claude returns final text response

4. Response Handling:
   - Stores both user and assistant messages
   - Returns formatted response with citations

Routes:
- POST /projects/<id>/chats/<id>/messages - Send message, get AI response
- POST /projects/<id>/chats/<id>/messages/stream - Send message, stream AI response
"""
import json
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, List, Tuple, Union

from flask import g, jsonify, request, current_app, Response, stream_with_context
from werkzeug.utils import secure_filename
from app.api.messages import messages_bp
from app.services.chat_services import main_chat_service
from app.services.data_services.chat_service import chat_service
from app.services.auth.rbac import get_request_identity
from app.services.integrations.claude.claude_service import (
    set_current_user_email,
    tag_chat_thread,
)
from app.services.integrations.supabase import storage_service
from app.utils.error_responses import error_response


_STREAM_SENTINEL = object()

# In-flight registry: chat_ids that currently have a streaming worker
# alive. A second POST for the same chat is rejected with 409 instead of
# being allowed to spawn a parallel worker. Prod logs at 07:27:27 showed
# two FreshdeskAgent instances (97c88b5c and b71721c2) starting in the
# same second for the same chat — that's a second /messages/stream POST
# landing while the first was still running. The frontend's send-lock
# fix prevents the rapid-click case; this server-side guard is the
# defense-in-depth for cross-tab, browser-retry, and any future caller
# paths that bypass the UI lock.
#
# Caveat: this set is per-gunicorn-worker. With workers > 1 the dedup
# only catches duplicates that happen to hash to the same worker.
# That's a pre-existing limitation; the §2.1 marker uses Supabase
# instead precisely to avoid this trap.
_in_flight_chats: set = set()
_in_flight_lock = threading.Lock()

# Inline chat-image attachment constraints. Anthropic's vision API caps
# at 5MB per image and supports png/jpeg/webp/gif. We cap at 10 images
# per message — more than enough for "drop a few screenshots" and keeps
# the multipart payload bounded.
_ALLOWED_ATTACHMENT_MIMES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
}
_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
_MAX_ATTACHMENTS_PER_MESSAGE = 10


def _parse_message_request(project_id: str, chat_id: str) -> Tuple[Any, Union[Tuple[Response, int], None]]:
    """
    Read the message text + any inline image attachments from the request,
    upload images to chat-attachments storage, and return the payload to
    pass to main_chat_service.

    Supports both `application/json` (text-only, legacy) and
    `multipart/form-data` (text + attachments). Returns a tuple of
    (user_message_payload, error_response). On error, error_response is
    a (jsonified, status_code) pair the route can return directly; on
    success, error_response is None.

    The payload is either a plain string (no attachments — current shape
    add_user_message has handled forever) or a list of content blocks
    (new shape — image blocks first, text block last). Both flow through
    add_user_message → JSONB storage → build_api_messages transparently.
    """
    content_type = request.content_type or ""

    if content_type.startswith("multipart/"):
        user_message_text = (request.form.get("message") or "").strip()
        upload_files = request.files.getlist("attachments")
    else:
        data = request.get_json(silent=True) or {}
        user_message_text = (data.get("message") or "").strip()
        upload_files = []

    if not user_message_text and not upload_files:
        return None, (jsonify({"success": False, "error": "Message or attachment required"}), 400)

    if len(upload_files) > _MAX_ATTACHMENTS_PER_MESSAGE:
        return None, (jsonify({
            "success": False,
            "error": f"Maximum {_MAX_ATTACHMENTS_PER_MESSAGE} attachments per message.",
        }), 400)

    # Track every successfully-uploaded path so we can roll them back on
    # any later failure in this loop. Without this, a partial failure
    # (e.g. file 1 uploads, file 2 fails MIME check) would orphan file 1
    # in the bucket — invisible until cascade-delete on chat removal.
    uploaded_paths: List[str] = []

    def _rollback_uploaded() -> None:
        for path in uploaded_paths:
            try:
                storage_service.delete_chat_attachment(path)
            except Exception:  # pragma: no cover — best-effort cleanup
                current_app.logger.warning(
                    "Rollback failed for chat attachment %s", path,
                )

    attachment_blocks: List[dict] = []
    for upload in upload_files:
        mime = (upload.content_type or "").lower()
        # Normalise jpg → jpeg so downstream MIME comparisons are consistent.
        if mime == "image/jpg":
            mime = "image/jpeg"
        if mime not in _ALLOWED_ATTACHMENT_MIMES:
            _rollback_uploaded()
            return None, (jsonify({
                "success": False,
                "error": f"Unsupported image format ({mime or 'unknown'}). Allowed: PNG, JPEG, WebP, GIF.",
            }), 400)

        data_bytes = upload.read()
        if not data_bytes:
            _rollback_uploaded()
            return None, (jsonify({"success": False, "error": "Empty attachment."}), 400)
        if len(data_bytes) > _MAX_ATTACHMENT_BYTES:
            _rollback_uploaded()
            return None, (jsonify({
                "success": False,
                "error": f"Image exceeds {_MAX_ATTACHMENT_BYTES // (1024*1024)}MB limit.",
            }), 400)

        attachment_id = uuid.uuid4().hex
        # secure_filename() returns "" for purely punctuation/Unicode names —
        # fall back to a generated name so the storage path isn't malformed.
        safe_name = secure_filename(upload.filename or "") or f"attachment-{attachment_id}"
        storage_path = storage_service.upload_chat_attachment(
            project_id=project_id,
            chat_id=chat_id,
            attachment_id=attachment_id,
            filename=safe_name,
            file_data=data_bytes,
            content_type=mime,
        )
        if not storage_path:
            _rollback_uploaded()
            return None, (jsonify({"success": False, "error": "Failed to store attachment."}), 500)

        uploaded_paths.append(storage_path)
        attachment_blocks.append({
            "type": "image",
            "storage_path": storage_path,
            "media_type": mime,
            "filename": safe_name,
            # Signed URL is a convenience for chat-history rendering. It's
            # short-lived (1h); _format_message_for_frontend re-signs on
            # subsequent reads.
            "url": storage_service.get_chat_attachment_url(storage_path) or "",
        })

    if attachment_blocks:
        # Image blocks come BEFORE text — Anthropic's vision docs recommend
        # this for best instruction-following ("here's an image, here's
        # what to do with it").
        user_message_payload: Union[str, list] = [
            *attachment_blocks,
            {"type": "text", "text": user_message_text or ""},
        ]
    else:
        user_message_payload = user_message_text

    return user_message_payload, None


def _format_sse(event_name: str, payload: dict | None = None) -> str:
    """Format a single SSE event chunk."""
    data = json.dumps(payload or {}, ensure_ascii=False)
    return f"event: {event_name}\ndata: {data}\n\n"


@messages_bp.route('/projects/<project_id>/chats/<chat_id>/messages', methods=['POST'])
def send_message(project_id, chat_id):
    """
    Send a message in a chat and get AI response.

    Educational Note: This endpoint is kept thin - all logic is delegated
    to main_chat_service. The service handles:
    1. Storing user message
    2. Building context with system prompt
    3. Calling Claude API
    4. Executing tool use loop
    5. Storing assistant response
    6. Syncing chat index

    Request Body:
        { "message": "Your question about the sources..." }

    Response:
        {
            "success": true,
            "user_message": { ... message object ... },
            "assistant_message": { ... message object with citations ... }
        }
    """
    try:
        user_message_payload, err = _parse_message_request(project_id, chat_id)
        if err is not None:
            return err

        # Same in-flight guard as the streaming route. Frontend's
        # streamMessage→sendMessage fallback (ChatPanel.tsx:742) lands here
        # when the stream fails before any event, so a stream that 502'd
        # mid-tool-execution can land its worker AND the fallback's worker
        # on the same chat in parallel without this check.
        with _in_flight_lock:
            if chat_id in _in_flight_chats:
                current_app.logger.info(
                    "Rejecting duplicate /messages for chat %s (already in flight)",
                    chat_id,
                )
                return jsonify({
                    'success': False,
                    'error': 'A response is already in progress for this chat.',
                }), 409
            _in_flight_chats.add(chat_id)

        try:
            # Delegate all processing to main_chat_service
            # This is the RAG + agentic loop entry point
            result = main_chat_service.send_message(
                project_id=project_id,
                chat_id=chat_id,
                user_message_text=user_message_payload,
            )
        finally:
            with _in_flight_lock:
                _in_flight_chats.discard(chat_id)

        return jsonify({
            'success': True,
            'user_message': result['user_message'],
            'assistant_message': result['assistant_message'],
            'sync': result.get('sync'),
        }), 200

    except ValueError as e:
        # Chat or project not found
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        return error_response(e, default_log="Error sending message")


@messages_bp.route('/projects/<project_id>/chats/<chat_id>/messages/stream', methods=['POST'])
def stream_message(project_id, chat_id):
    """
    Send a message in a chat and stream back assistant deltas as SSE.

    The final saved assistant message is emitted as an `assistant_done` event.
    """
    user_message_payload, err = _parse_message_request(project_id, chat_id)
    if err is not None:
        return err

    # In-flight dedup. Acquire the slot atomically before parsing identity
    # or starting the worker so two concurrent POSTs can't both pass the
    # "is this chat in flight?" check. The slot is released in the worker's
    # finally below; the failure path (claim rejected) returns 409 without
    # touching identity/queue/threads.
    with _in_flight_lock:
        if chat_id in _in_flight_chats:
            current_app.logger.info(
                "Rejecting duplicate /messages/stream for chat %s (already in flight)",
                chat_id,
            )
            return jsonify({
                "success": False,
                "error": "A response is already in progress for this chat. Wait for it to finish or press Stop.",
            }), 409
        _in_flight_chats.add(chat_id)

    identity = get_request_identity()
    user_id = identity.user_id
    # Capture email here (request context is alive); we'll re-stash it
    # inside the worker thread below so Opik traces still get tagged
    # after we leave the Flask request scope.
    user_email = identity.email if identity.is_authenticated else None
    # Capture the req_id while we're still in the Flask request context.
    # The worker thread re-stashes it via set_worker_req_id() so that
    # PROXY_DISCONNECT_PERSIST + other background traces stay grep-able
    # against the originating frontend request_id.
    parent_req_id = getattr(g, "req_id", "-")
    app = current_app._get_current_object()
    # Bounded so the worker can't accumulate hundreds of KB of unread events
    # after the client disconnects. 512 is well above the steady-state size
    # of an in-flight stream (a few dozen events queued at most), so a normal
    # slow consumer just back-pressures the worker via the blocking put.
    event_queue: "queue.Queue[object]" = queue.Queue(maxsize=512)
    # Two flags, distinct semantics:
    #
    # - cancel_event: short-circuit signal for the agent loop. Set when EITHER
    #   the user clicked Stop OR the proxy/browser closed the SSE connection.
    #   In both cases the worker should stop persisting tool calls and final
    #   text — without this, Flask's stream_with_context keeps the worker
    #   thread running and we'd write a half-baked response (the "two answers
    #   on resend" symptom).
    #
    # - user_stop_event: labeling signal. Set ONLY when /messages/stop was
    #   posted (the user explicitly clicked Stop in the UI). Drives the
    #   "(stopped by user)" suffix in main_chat_service. Without this flag,
    #   a proxy idle-timeout (Coolify/nginx) silently mislabeled real
    #   responses as user-stopped — that's Delta's Symptom 9.
    cancel_event = threading.Event()
    user_stop_event = threading.Event()

    def emit(event_name: str, payload: dict) -> None:
        # After the client has disconnected, nothing reads the queue — drop
        # the event instead of blocking forever on a bounded queue. The
        # worker checks cancel_event between iterations and bails on its
        # own; this just avoids it getting stuck on `put` first.
        if cancel_event.is_set():
            return
        try:
            event_queue.put(_format_sse(event_name, payload), timeout=5)
        except queue.Full:
            app.logger.warning("SSE queue full — dropping event %s", event_name)

    def worker() -> None:
        # Re-stash user_email inside the worker thread so claude_service
        # can tag Opik traces even though Flask's request context doesn't
        # cross the thread boundary. ContextVars are per-thread, so this
        # only affects this worker.
        set_current_user_email(user_email)
        # Same shape: re-stash the parent req_id in this thread's
        # ContextVar so every log line emitted from main_chat_service
        # below carries the originating request's req_id instead of "-".
        # Without this the most user-facing trace (PROXY_DISCONNECT_PERSIST)
        # loses its correlation key precisely when we need it most.
        from app.utils.request_context import set_worker_req_id
        set_worker_req_id(parent_req_id)
        # Fire-and-forget: tag the Opik thread with user identity once per
        # chat so the thread list is filterable by user. Deduped in
        # claude_service so repeated sends in the same chat are cheap.
        tag_chat_thread(chat_id=chat_id, user_email=user_email, project_id=project_id)
        try:
            main_chat_service.stream_message(
                project_id=project_id,
                chat_id=chat_id,
                user_message_text=user_message_payload,
                user_id=user_id,
                on_event=emit,
                cancel_event=cancel_event,
                user_stop_event=user_stop_event,
            )
        except ValueError as exc:
            emit("error", {"message": str(exc)})
        except Exception as exc:
            app.logger.error(f"Error streaming message: {exc}")
            emit("error", {"message": str(exc)})
        finally:
            # Release the in-flight slot BEFORE the sentinel so a follow-up
            # POST (e.g. the user starting the next message the instant the
            # current one finishes) doesn't race the slot's release. Order
            # matters: removing from the set must be safe even if generate()
            # has already torn down due to GeneratorExit.
            with _in_flight_lock:
                _in_flight_chats.discard(chat_id)
            # No explicit clear of chats.user_stopped_at: the freshness
            # check in GeneratorExit (stop-timestamp > stream-start) means
            # a stale value from a previous message never triggers a
            # false positive on the next stream.
            event_queue.put(_STREAM_SENTINEL)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    # Tracking state for SSE_CLOSE_TRACE — answers the central question
    # behind Symptom 9 ("stopped by user when not actually stopped"):
    # was the disconnect a proxy timeout (elapsed >> 0, heartbeats fired)
    # or a real user abort (elapsed ~0, no heartbeats needed)?
    #
    # `stream_started_wallclock` is the wall-clock anchor we compare
    # against `chats.user_stopped_at` to decide whether a /stop signal
    # arrived DURING this stream (real user-stop) or was left over from
    # a previous message (stale — ignore). monotonic() is used for
    # latency math because it's immune to clock jumps; wall-clock is
    # used for the cross-row comparison because that's what the DB has.
    stream_started_at = time.monotonic()
    stream_started_wallclock = datetime.now(timezone.utc)
    last_event_at = stream_started_at
    heartbeat_count = 0

    def generate():
        # Heartbeat keeps the SSE connection alive while long-running tools
        # (e.g. FreshdeskAnalyzerAgent's 7-15 iterations) run silently between
        # `emit()` calls. Without it, proxies (nginx/Coolify) drop the idle
        # connection at ~60s, GeneratorExit fires, cancel_event is set, and
        # the worker mislabels the response as "(stopped by user)". The colon
        # prefix is an SSE comment — browsers ignore it but the bytes prevent
        # idle-timeout.
        nonlocal last_event_at, heartbeat_count
        try:
            while True:
                try:
                    item = event_queue.get(timeout=15)
                except queue.Empty:
                    heartbeat_count += 1
                    yield ": heartbeat\n\n"
                    continue
                if item is _STREAM_SENTINEL:
                    break
                last_event_at = time.monotonic()
                yield item
        except GeneratorExit:
            # Connection closed for one of three reasons:
            #   1. User explicitly clicked Stop in the UI (POST /messages/stop
            #      wrote chats.user_stopped_at = NOW()).
            #   2. The user navigated away or closed the tab (browser
            #      aborts the fetch).
            #   3. The proxy (Coolify/nginx) gave up on an idle SSE
            #      connection despite our 15s heartbeats.
            #
            # ORDERING MATTERS: cancel_event.set() FIRST, BEFORE the Supabase
            # lookup for the user-stop label. The Supabase call can hang for
            # 30-120s on the OS-default socket timeout if Supabase/Kong is
            # unreachable — which is exactly the burst-load scenario this PR
            # targets. With the old ordering (label first, cancel last), the
            # worker thread kept running Claude tool calls for the entire
            # hang window, burning tokens and CPU on a request the user has
            # already abandoned.
            #
            # The labeling logic can race the worker (rare — worker is
            # usually mid-Claude-call for seconds when GeneratorExit fires,
            # giving the Supabase query plenty of time to finish before the
            # worker reaches the labeling branch in main_chat_service). On
            # the rare race, a real user-stop gets labeled as proxy-
            # disconnect; that's a UX wart, not data loss, and same UX as
            # pre-PR-283. Acceptable trade-off for guaranteed worker
            # termination on Supabase outages.
            cancel_event.set()

            # cancel_event is set in all three cases — the worker stops
            # persisting. user_stop_event is set ONLY in case 1, so the
            # final assistant message only gets the "(stopped by user)"
            # label when that's actually what happened.
            #
            # Cross-worker correctness: chats.user_stopped_at is in
            # Supabase, so the POST /messages/stop on worker A and the
            # SSE worker on worker B see the same source of truth. The
            # in-process set we used pre-H2 only worked when workers=1.
            # Freshness check: a stop timestamp from BEFORE this stream
            # started is from a previous message — ignore it (M1 race).
            try:
                user_stopped_at_iso = chat_service.get_user_stopped_at(project_id, chat_id)
            except Exception as supabase_exc:
                # Defensive: get_user_stopped_at already catches everything,
                # but if it ever raises (e.g. a new exception type after a
                # supabase-py upgrade), default to proxy_disconnect rather
                # than crashing the cleanup path. The worker has already
                # been told to stop above; this is purely for labeling.
                app.logger.warning(
                    "SSE_CLOSE_TRACE chat=%s supabase_lookup_failed err=%s:%s "
                    "— defaulting label to connection_dropped",
                    chat_id, type(supabase_exc).__name__, str(supabase_exc)[:120],
                )
                user_stopped_at_iso = None
            was_user_stop = False
            if user_stopped_at_iso:
                try:
                    user_stopped_at = datetime.fromisoformat(
                        user_stopped_at_iso.replace("Z", "+00:00")
                    )
                    was_user_stop = user_stopped_at > stream_started_wallclock
                except (ValueError, TypeError):
                    # Malformed timestamp — conservative default: not user-stop.
                    was_user_stop = False
            if was_user_stop:
                user_stop_event.set()
            now = time.monotonic()
            app.logger.warning(
                "SSE_CLOSE_TRACE chat=%s reason=%s elapsed_total=%.2fs "
                "elapsed_since_last_event=%.2fs heartbeats_sent=%d",
                chat_id,
                "user_stop" if was_user_stop else "connection_dropped",
                now - stream_started_at,
                now - last_event_at, heartbeat_count,
            )
            raise

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(generate()), headers=headers)


@messages_bp.route('/projects/<project_id>/chats/<chat_id>/messages/stop', methods=['POST'])
def stop_message(project_id, chat_id):
    """
    Explicit "user clicked Stop" signal.

    Writes `chats.user_stopped_at = NOW()` (scoped to project_id, so a
    user can't poison another tenant's chat). When the SSE GeneratorExit
    fires immediately after — because the frontend also aborts the
    AbortController — the worker reads `user_stopped_at` and compares
    against its own stream-start wall-clock to decide whether to apply
    the "(stopped by user)" label.

    The DB is the source of truth because gunicorn workers don't share
    memory: POST /messages/stop and POST /messages/stream commonly land
    on different workers. The pre-H2 in-process set worked only when
    workers=1.

    Idempotent — repeated POSTs just rewrite the timestamp. 404 when the
    project doesn't own the chat (the SQL WHERE clause filters cross-
    project writes; mirrors the verify_project_access blueprint hook on
    messages_bp at the chat level).
    """
    try:
        updated = chat_service.mark_user_stopped(project_id, chat_id)
    except Exception as e:
        return error_response(e, default_log=f"Error marking chat {chat_id} as user-stopped")
    if not updated:
        return jsonify({
            "success": False,
            "error": "Chat not found or not accessible.",
        }), 404
    return jsonify({"success": True}), 200
