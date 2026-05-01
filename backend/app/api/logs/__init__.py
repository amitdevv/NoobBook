"""
Logs API blueprint — admin diagnostic bundle + client-side error capture.

Routes (registered under /api/v1):
  POST  /logs/client          (any authenticated user) — record a browser error
  GET   /logs/recent          (admin)                  — last N error/warning lines
  GET   /logs/bundle          (admin)                  — ZIP support bundle
  POST  /logs/clear           (admin)                  — truncate log file + archives
"""
from flask import Blueprint

logs_bp = Blueprint('logs', __name__)

from app.api.logs import routes  # noqa: F401,E402
