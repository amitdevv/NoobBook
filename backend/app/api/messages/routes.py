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
import uuid
from typing import Any, List, Tuple, Union

from flask import jsonify, request, current_app, Response, stream_with_context
from werkzeug.utils import secure_filename
from app.api.messages import messages_bp
from app.services.chat_services import main_chat_service
from app.services.auth.rbac import get_request_identity
from app.services.integrations.claude.claude_service import (
    set_current_user_email,
    tag_chat_thread,
)
from app.services.integrations.supabase import storage_service


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
        current_app.logger.error(f"Error sending message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
    app = current_app._get_current_object()
    # Bounded so the worker can't accumulate hundreds of KB of unread events
    # after the client disconnects. 512 is well above the steady-state size
    # of an in-flight stream (a few dozen events queued at most), so a normal
    # slow consumer just back-pressures the worker via the blocking put.
    event_queue: "queue.Queue[object]" = queue.Queue(maxsize=512)
    # Cancel flag — set when the SSE generator is closed (client disconnect /
    # frontend AbortController). Plumbed into the chat service so the
    # assistant message isn't persisted after the user clicks Stop. Without
    # this, Flask's stream_with_context keeps the worker thread running and
    # we'd write the half-baked response to DB, producing the "two answers
    # on resend" symptom Neel reported.
    cancel_event = threading.Event()

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
            event_queue.put(_STREAM_SENTINEL)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def generate():
        # Heartbeat keeps the SSE connection alive while long-running tools
        # (e.g. FreshdeskAnalyzerAgent's 7-15 iterations) run silently between
        # `emit()` calls. Without it, proxies (nginx/Coolify) drop the idle
        # connection at ~60s, GeneratorExit fires, cancel_event is set, and
        # the worker mislabels the response as "(stopped by user)". The colon
        # prefix is an SSE comment — browsers ignore it but the bytes prevent
        # idle-timeout.
        try:
            while True:
                try:
                    item = event_queue.get(timeout=15)
                except queue.Empty:
                    yield ": heartbeat\n\n"
                    continue
                if item is _STREAM_SENTINEL:
                    break
                yield item
        except GeneratorExit:
            # Client disconnected (browser navigation, AbortController, etc.).
            # Tell the worker to stop persisting before re-raising so Flask
            # can clean up the response.
            cancel_event.set()
            raise

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(generate()), headers=headers)
