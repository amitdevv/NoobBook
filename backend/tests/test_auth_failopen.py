"""
Regression tests for §2.3 — slow-path fail-open in auth_middleware.

Background:
  Before §2.3, the slow-path branch (JWT_SECRET unset OR fast-path raised an
  unexpected exception) had no fail-open: any GoTrue exception → return None
  → 401 → frontend logout cascade. That's the most plausible mechanism
  behind Delta's Symptom 1 (logout while 4-5 DBs are processing — burst
  load on GoTrue surfaces transient errors).

  The fix mirrors the fast-path fail-open: on GoTrue exception, decode the
  JWT WITH JWT_SECRET to verify the signature, then extract `sub`. Expiry
  is still enforced so stale tokens can't ride this branch. Successful
  fail-open caches the result for 60s.

  Security invariant: signature verification is mandatory. If JWT_SECRET is
  not configured, fail-open is disabled and the caller gets None. (Earlier
  drafts of §2.3 accepted the unverified `sub` claim, which let any forged
  JWT impersonate any user during a GoTrue outage — see
  `test_forged_token_is_rejected_when_jwt_secret_unset` below.)

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


_TEST_SECRET = "test-jwt-secret-for-failopen"


@pytest.fixture
def minimal_app() -> Flask:
    """A tiny Flask app — just enough to provide request context."""
    return Flask(__name__)


def _make_token(sub: str, expires_in: int = 3600, secret: str = _TEST_SECRET) -> str:
    """Build a JWT signed with the test secret. Tests that exercise the
    secure fail-open path must use this so the signature verifies."""
    payload = {
        "sub": sub,
        "exp": int(time.time()) + expires_in,
        "aud": "authenticated",
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def slow_path_with_secret(monkeypatch):
    """Force the slow path but keep JWT_SECRET set so signature-verified
    fail-open is available.

    We patch _JWT_SECRET on the module rather than via os.environ because
    the constant is read once at import time.
    """
    monkeypatch.setattr(auth_middleware, "_JWT_SECRET", _TEST_SECRET)
    with auth_middleware._cache_lock:
        auth_middleware._token_cache.clear()
        auth_middleware._token_locks.clear()
    yield


@pytest.fixture
def slow_path_no_secret(monkeypatch):
    """Force the slow path WITHOUT JWT_SECRET — fail-open must be disabled."""
    monkeypatch.setattr(auth_middleware, "_JWT_SECRET", "")
    with auth_middleware._cache_lock:
        auth_middleware._token_cache.clear()
        auth_middleware._token_locks.clear()
    yield


class TestSlowPathFailOpen:

    def test_failopen_returns_user_id_when_gotrue_raises(self, minimal_app, slow_path_with_secret):
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
        # After: we trust the locally signature-verified sub for 60s.
        assert result == "user-42"

    def test_failopen_caches_result(self, minimal_app, slow_path_with_secret):
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
                # First call: fail-open trusts the locally-verified sub.
                assert auth_middleware.validate_token() == "user-cache"
                # Second call within the cache TTL should NOT hit GoTrue again.
                assert auth_middleware.validate_token() == "user-cache"
                # Exactly 1 GoTrue call across both validate_token() calls.
                assert mock_client.return_value.auth.get_user.call_count == 1

    def test_failopen_rejects_expired_token(self, minimal_app, slow_path_with_secret):
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

    def test_failopen_rejects_malformed_token(self, minimal_app, slow_path_with_secret):
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

    def test_no_token_returns_none(self, minimal_app, slow_path_with_secret):
        """Sanity-check: missing Authorization header still fails (we don't
        want the fail-open path to be confused with "no auth required")."""
        with minimal_app.test_request_context("/api/v1/foo"):
            result = auth_middleware.validate_token()
        assert result is None

    def test_forged_token_rejected_during_outage(self, minimal_app, slow_path_with_secret):
        """P1: a JWT signed with the WRONG secret must not pass fail-open
        even when GoTrue is unreachable. Otherwise any attacker could
        impersonate any user by minting `sub=<victim_uuid>` during an
        outage."""
        forged = _make_token("victim-uuid", secret="attacker-controlled-secret")
        with minimal_app.test_request_context(
            "/api/v1/foo",
            headers={"Authorization": f"Bearer {forged}"},
        ):
            with patch(
                "app.utils.auth_middleware.get_auth_verifier_client",
            ) as mock_client:
                mock_client.return_value.auth.get_user.side_effect = (
                    ConnectionError("GoTrue down")
                )
                result = auth_middleware.validate_token()
        assert result is None, "Forged JWTs must not fail-open."

    def test_failopen_disabled_when_jwt_secret_unset(self, minimal_app, slow_path_no_secret):
        """If JWT_SECRET is not configured, we cannot verify the signature
        locally — fail-open is disabled to keep the attack surface closed.
        Genuine users with a recently-validated token still pass via the
        cache (covered in test_failopen_caches_result above)."""
        token = _make_token("user-cant-verify")
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
        assert result is None
