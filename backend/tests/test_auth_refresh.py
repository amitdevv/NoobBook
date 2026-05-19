"""
Backend contract tests for POST /api/v1/auth/refresh.

Pins the response shapes that the frontend's cross-tab refresh-token
rotation fix branches off:
  - HTTP 200 + {success: true, session: {access_token, refresh_token}}
    when the refresh succeeded.
  - HTTP 401 + {success: false, error: "Token refresh failed"}
    when supabase-py raised "Invalid Refresh Token: Already Used"
    (the GoTrue rotation race that the cross-tab fix in
    frontend/src/lib/api/client.ts depends on).

A future supabase-py upgrade could change the error shape, and the
frontend's reactive cross-tab branch depends on `status === 401`. Pinning
that here protects against silent contract drift.
"""
from __future__ import annotations

from unittest.mock import patch

from flask import Flask

from app.api.auth import auth_bp


def _app() -> Flask:
    """Build a minimal Flask app that mounts just the auth blueprint.

    Mirrors the inline-Flask pattern from test_proxy_disconnect.py and
    test_auth_failopen.py — keeps these tests isolated from the broader
    `create_app('testing')` fixture issue that pytest-flask exposes in
    this venv's Python 3.14.
    """
    a = Flask(__name__)
    a.register_blueprint(auth_bp, url_prefix='/api/v1')
    return a


class TestAuthRefreshContract:

    def test_success_returns_200_with_session_body(self):
        with patch(
            'app.api.auth.routes.auth_service.refresh_with_token',
            return_value={
                'success': True,
                'session': {
                    'access_token': 'access-rotated',
                    'refresh_token': 'refresh-rotated',
                    'expires_in': 3600,
                    'token_type': 'bearer',
                },
            },
        ):
            client = _app().test_client()
            resp = client.post('/api/v1/auth/refresh', json={'refresh_token': 'r'})

        assert resp.status_code == 200
        assert resp.json['success'] is True
        assert resp.json['session']['access_token'] == 'access-rotated'
        assert resp.json['session']['refresh_token'] == 'refresh-rotated'

    def test_already_used_token_returns_401_matching_frontend_contract(self):
        """The exact failure mode behind Delta's spontaneous logouts.

        When GoTrue rejects a refresh with refresh_token_already_used (HTTP
        400 from /token), supabase-py's `refresh_session(rt)` raises and
        the service wraps it as `{success: False, error: "Token refresh
        failed"}`. The endpoint must surface this as HTTP 401 so the
        frontend's `handle401Error` / cross-tab dedup branches see the
        status they're written against.
        """
        with patch(
            'app.api.auth.routes.auth_service.refresh_with_token',
            return_value={'success': False, 'error': 'Token refresh failed'},
        ):
            client = _app().test_client()
            resp = client.post('/api/v1/auth/refresh', json={'refresh_token': 'r'})

        assert resp.status_code == 401
        assert resp.json['success'] is False
        assert resp.json['error'] == 'Token refresh failed'

    def test_missing_refresh_token_returns_400(self):
        """Sanity check on the input-validation path — body must include
        `refresh_token`. Returns 400, not 401, so the frontend doesn't
        treat a malformed-call as a rotation-race signal."""
        client = _app().test_client()
        resp = client.post('/api/v1/auth/refresh', json={})

        assert resp.status_code == 400
        assert resp.json['success'] is False
        assert 'refresh_token' in resp.json['error']
