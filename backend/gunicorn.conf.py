"""
Gunicorn configuration for NoobBook production deployment.
"""
import os

bind = f"0.0.0.0:{os.getenv('PORT', '5001')}"

# Multiple workers so a single blocking job (PDF batch, Playwright launch,
# ffmpeg, LibreOffice subprocess) cannot wedge the entire backend.
# Flask-SocketIO is initialized but no @socketio.on / socketio.emit handlers
# are registered, so cross-worker state coordination isn't required and
# raising workers above 1 is safe. Override via GUNICORN_WORKERS env var.
workers = int(os.getenv("GUNICORN_WORKERS", "4"))

worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"

# Concurrent greenlets per worker. With 4 workers x 200 = 800 concurrent
# in-flight requests possible.
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "200"))

# Request timeout: if a worker doesn't respond within this time, Gunicorn
# kills and restarts it. 600s gives long Claude tool loops AND gigabyte
# uploads on slow connections enough headroom (1GB at 2MB/s is ~9min).
timeout = 600

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
