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

from flask import jsonify, request, current_app, Response, stream_with_context
from app.api.messages import messages_bp
from app.services.chat_services import main_chat_service
from app.services.auth.rbac import get_request_identity


_STREAM_SENTINEL = object()


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
        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400

        user_message_text = data['message']

        # Delegate all processing to main_chat_service
        # This is the RAG + agentic loop entry point
        result = main_chat_service.send_message(
            project_id=project_id,
            chat_id=chat_id,
            user_message_text=user_message_text
        )

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
    data = request.get_json()

    if not data or 'message' not in data:
        return jsonify({
            'success': False,
            'error': 'Message is required'
        }), 400

    user_message_text = data['message']
    identity = get_request_identity()
    user_id = identity.user_id
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
        try:
            main_chat_service.stream_message(
                project_id=project_id,
                chat_id=chat_id,
                user_message_text=user_message_text,
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
            event_queue.put(_STREAM_SENTINEL)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def generate():
        try:
            while True:
                item = event_queue.get()
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
