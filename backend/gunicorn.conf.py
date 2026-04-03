"""
Gunicorn configuration for NoobBook production deployment.

Educational Note: Gunicorn is a production-grade WSGI server that replaces
Flask's built-in Werkzeug dev server. Key differences:
- Werkzeug: single-process, no crash recovery, not designed for real traffic
- Gunicorn + gevent: handles hundreds of concurrent connections via greenlets
  (cooperative multitasking), auto-restarts crashed workers, proper timeouts

We use gevent-websocket worker class because Flask-SocketIO needs WebSocket
support. With gevent, a single worker can handle many concurrent I/O-bound
requests (Claude API calls, Supabase queries) without blocking.
"""
import os

# Bind to the configured port (default 5001)
bind = f"0.0.0.0:{os.getenv('PORT', '5001')}"

# Flask-SocketIO requires exactly 1 worker when not using a message queue
# (like Redis). This is fine because gevent handles concurrency via greenlets,
# not OS processes. One gevent worker can serve hundreds of concurrent requests.
workers = 1

# GeventWebSocketWorker supports both regular HTTP and WebSocket connections.
# It calls monkey.patch_all() automatically in each worker's init_process()
# before the app is loaded — no manual monkey-patching needed in app code.
# NOTE: Do NOT set preload_app = True. That would monkey-patch the master
# process before forking, breaking signal handling and graceful shutdown.
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"

# Request timeout: if a worker doesn't respond within this time, Gunicorn
# kills and restarts it. Set to 300s to match nginx proxy_read_timeout
# and allow for long Claude API calls with tool loops.
timeout = 300

# Time to finish serving requests after receiving SIGTERM
graceful_timeout = 30

# Keep-alive connections to reduce TCP handshake overhead
keepalive = 5

# Restart workers periodically to prevent memory leaks from long-running
# processes (LibreOffice, Playwright, large file processing).
# With workers=1, recycling drops ALL active connections (SSE streams,
# WebSockets), so keep the threshold high enough to avoid frequent drops.
max_requests = 5000
max_requests_jitter = 200

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
