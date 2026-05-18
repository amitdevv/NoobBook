"""
Regression tests for §2.3 — slow-path fail-open in auth_middleware.

Background:
  Before §2.3, the slow-path branch (JWT_SECRET unset OR fast-path raised an
  unexpected exception) had no fail-open: any GoTrue exception → return None
  → 401 → frontend logout cascade. That's the most plausible mechanism
  behind Delta's Symptom 1 (logout while 4-5 DBs are processing — burst
  load on GoTrue surfaces transient errors).

  The fix mirrors the fast-path fail-open: on GoTrue exception, decode the
  JWT WITHOUT signature verification to extract `sub`. Expiry is still
  enforced (jwt.decode raises ExpiredSignatureError) so stale tokens can't
  ride this branch. Successful fail-open caches the result for 60s.

Notes on the fixture strategy:
  The conftest `app` fixture goes through `create_app("testing")` which
  pulls in the whole service graph and gets tangled with pytest-flask's
  autouse `_configure_application` hook in this repo's Python 3.14 venv.
  We don't need any of that — `validate_token()` only touches Flask's
  request context for `request.headers` / `request.args`. So we build a
  minimal Flask app inline and drive test_request_context off it. Fast,
  no autouse coupling, and orthogonal to the rest of the suite.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import jwt
import pytest
from flask import Flask

from app.utils import auth_middleware


@pytest.fixture
def minimal_app() -> Flask:
    """A tiny Flask app — just enough to provide request context."""
    return Flask(__name__)


def _make_token(sub: str, expires_in: int = 3600, secret: str = "irrelevant") -> str:
    """Build a JWT with a given sub and expiry. The signature is signed with
    a throwaway secret because the fail-open path doesn't verify it."""
    payload = {
        "sub": sub,
        "exp": int(time.time()) + expires_in,
        "aud": "authenticated",
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def slow_path_only(monkeypatch):
    """Force the slow path by unsetting JWT_SECRET in the module.

    The fast-path constant is read once at import time, so we have to
    patch it on the module rather than via os.environ.
    """
    monkeypatch.setattr(auth_middleware, "_JWT_SECRET", "")
    # Clear the per-process token cache so each test starts fresh.
    with auth_middleware._cache_lock:
        auth_middleware._token_cache.clear()
        auth_middleware._token_locks.clear()
    yield


class TestSlowPathFailOpen:

    def test_failopen_returns_user_id_when_gotrue_raises(self, minimal_app, slow_path_only):
        token = _make_token("user-42")
        with minimal_app.test_request_context(
            "/api/v1/foo",
            headers={"Authorization": f"Bearer {token}"},
        ):
            with patch(
                "app.utils.auth_middleware.get_auth_verifier_client",
            ) as mock_client:
                # Simulate GoTrue blip — auth.get_user raises.
                mock_client.return_value.auth.get_user.side_effect = (
                    ConnectionError("GoTrue unreachable")
                )
                result = auth_middleware.validate_token()
        # Before the fix: result would be None (user logged out).
        # After:           we trust the locally-decoded sub for 60s.
        assert result == "user-42"

    def test_failopen_caches_result(self, minimal_app, slow_path_only):
        token = _make_token("user-cache")
        with minimal_app.test_request_context(
            "/api/v1/foo",
            headers={"Authorization": f"Bearer {token}"},
        ):
            with patch(
                "app.utils.auth_middleware.get_auth_verifier_client",
            ) as mock_client:
                mock_client.return_value.auth.get_user.side_effect = (
                    ConnectionError("blip")
                )
                # First call: fail-open trusts the locally-decoded sub.
                assert auth_middleware.validate_token() == "user-cache"
                # Second call within the cache TTL should NOT hit GoTrue again.
                assert auth_middleware.validate_token() == "user-cache"
                # Exactly 1 GoTrue call across both validate_token() calls.
                assert mock_client.return_value.auth.get_user.call_count == 1

    def test_failopen_rejects_expired_token(self, minimal_app, slow_path_only):
        """Expiry is still enforced — a stale token can't ride the fail-open."""
        token = _make_token("user-stale", expires_in=-60)
        with minimal_app.test_request_context(
            "/api/v1/foo",
            headers={"Authorization": f"Bearer {token}"},
        ):
            with patch(
                "app.utils.auth_middleware.get_auth_verifier_client",
            ) as mock_client:
                mock_client.return_value.auth.get_user.side_effect = (
                    ConnectionError("blip")
                )
                result = auth_middleware.validate_token()
        assert result is None, "Expired tokens must not fail-open."

    def test_failopen_rejects_malformed_token(self, minimal_app, slow_path_only):
        """Garbage in the Authorization header → no auth (fail-open requires
        a structurally valid JWT)."""
        with minimal_app.test_request_context(
            "/api/v1/foo",
            headers={"Authorization": "Bearer not-a-real-jwt-just-some-string"},
        ):
            with patch(
                "app.utils.auth_middleware.get_auth_verifier_client",
            ) as mock_client:
                mock_client.return_value.auth.get_user.side_effect = (
                    ConnectionError("blip")
                )
                result = auth_middleware.validate_token()
        assert result is None

    def test_no_token_returns_none(self, minimal_app, slow_path_only):
        """Sanity-check: missing Authorization header still fails (we don't
        want the fail-open path to be confused with "no auth required")."""
        with minimal_app.test_request_context("/api/v1/foo"):
            result = auth_middleware.validate_token()
        assert result is None
