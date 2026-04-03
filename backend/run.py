"""
Main entry point for NoobBook backend.

Educational Note: This file creates and runs the Flask application.
We keep it separate from the app factory to maintain clean separation
of concerns and make testing easier.

In production, Gunicorn imports this module to get the `app` object.
In development, this file is run directly via `python run.py`.
"""
import os
import logging
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Load .env FIRST so FLASK_ENV is visible to all module-level code
# (e.g. _async_mode in app/__init__.py reads FLASK_ENV at import time).
load_dotenv()

logger = logging.getLogger(__name__)


def clear_pycache():
    """
    Clear __pycache__ folders in the project code (excluding virtual environment).

    Educational Note: Python creates __pycache__ folders containing
    compiled bytecode (.pyc files). Clearing these on startup ensures
    fresh compilation and avoids stale cache issues during development.
    """
    backend_dir = Path(__file__).parent
    pycache_count = 0

    # Folders to skip (virtual environments, node_modules, etc.)
    skip_folders = {'myvenv', 'venv', '.venv', 'env', 'node_modules', '.git'}

    for pycache_dir in backend_dir.rglob("__pycache__"):
        # Skip if any parent folder is in skip_folders
        if any(part in skip_folders for part in pycache_dir.parts):
            continue
        try:
            shutil.rmtree(pycache_dir)
            pycache_count += 1
        except Exception as e:
            logger.warning("Could not delete %s: %s", pycache_dir, e)

    if pycache_count > 0:
        logger.debug("Cleared %s __pycache__ folders", pycache_count)


# Only clear pycache in development — in production, bytecode cache
# speeds up module loading and shouldn't be deleted on every worker start.
if os.getenv('FLASK_ENV') != 'production':
    clear_pycache()

from app import create_app, socketio

# Get configuration name from environment or use default
config_name = os.getenv('FLASK_ENV', 'development')

# Create the Flask application
app = create_app(config_name)


if __name__ == '__main__':
    """
    Run the Flask application.

    Educational Note: We use socketio.run instead of app.run when
    using Flask-SocketIO for WebSocket support (real-time features).
    """
    port = int(os.getenv('PORT', 5001))
    debug = config_name == 'development'

    logger.info("NoobBook Backend Server — http://localhost:%s (%s, debug=%s)", port, config_name, debug)

    # Run with SocketIO for WebSocket support
    socketio.run(
        app,
        host='0.0.0.0',  # Allow connections from any IP
        port=port,
        debug=debug,
        use_reloader=debug,  # Auto-reload on code changes in debug mode
        allow_unsafe_werkzeug=True  # Allow Werkzeug dev server (required for Flask-SocketIO)
    )