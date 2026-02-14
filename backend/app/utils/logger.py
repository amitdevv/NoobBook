"""
Logging configuration for NoobBook backend.

Sets up structured logging with consistent format across all modules.
Usage: import logging; logger = logging.getLogger(__name__)
"""
import logging
import sys


def setup_logging(log_level: str = "DEBUG") -> None:
    """
    Configure the root logger with a human-readable format.

    Called once at app startup in create_app(). All modules that use
    logging.getLogger(__name__) will inherit this configuration.
    """
    level = getattr(logging, log_level.upper(), logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers on reloads
    root.handlers = [handler]

    # Quiet noisy third-party loggers
    for name in ("urllib3", "werkzeug", "httpcore", "httpx", "hpack", "PIL"):
        logging.getLogger(name).setLevel(logging.WARNING)
