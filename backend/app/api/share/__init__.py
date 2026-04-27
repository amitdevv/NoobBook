"""
Share API Blueprint — viewer-side endpoints (Roadmap #15).

Mounted under ``/api/v1/share/*``. Routes here are reachable WITHOUT a
JWT for public-mode shares; the global ``before_request`` hook
whitelists this prefix and the per-route ``@require_share_token``
decorator runs the actual access check.

Routes:
    GET  /share/<token>                                       — share root
    GET  /share/<token>/chats/<chat_id>                       — full chat
    GET  /share/<token>/chats/<chat_id>/citations/<chunk_id>  — citation tooltip
    GET  /share/<token>/studio/<kind>/<job_id>/<filename>     — studio artifact proxy
    POST /share/<token>/chats/<chat_id>/fork                  — fork into viewer's workspace
"""
from flask import Blueprint

share_bp = Blueprint('share', __name__)

from app.api.share import routes  # noqa: F401, E402
