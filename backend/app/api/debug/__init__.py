"""
Debug API blueprint — admin-only diagnostic endpoints.

Routes (registered under /api/v1):
  GET  /debug/supabase-state   (admin) — confirms whether the data singleton's
                                          Authorization header has been flipped
                                          off service_role (the supabase-py
                                          2.15.0 listener-pollution bug).
  GET  /debug/stats             (admin) — in-flight chat count, token cache
                                          size, background queue depth.

These exist to give operators (and us) a 1-second live look at process state
during an incident, without `docker exec` access.
"""
from flask import Blueprint

debug_bp = Blueprint("debug", __name__)

from app.api.debug import routes  # noqa: F401,E402
