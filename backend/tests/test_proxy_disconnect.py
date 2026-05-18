"""
Regression tests for §2.1 — user-stop vs proxy-disconnect distinction.

Background:
  Before §2.1 the SSE generator's `except GeneratorExit` always set a single
  `cancel_event`, and `main_chat_service` then labeled the persisted
  assistant message "(stopped by user)" regardless of whether the user
  actually clicked Stop. Proxy idle-timeouts (Coolify/nginx dropping idle
  SSE connections) produced false positives — that was Delta's Symptom 9.

  The first iteration used an in-process `_user_stopped_chats` set. Code
  review (H2) flagged that this breaks the moment gunicorn runs more than
  one worker. The second iteration moves the marker to a `user_stopped_at`
  TIMESTAMPTZ column on the `chats` table (migration 00042). The SSE
  worker reads it on GeneratorExit and compares against its own
  stream-start wall-clock — a fresher timestamp means the user really did
  click Stop, an older one is leftover from a previous message (the M1
  race) and is ignored.

These tests verify the routing decisions and the labeling matrix, not the
Claude tool loop itself.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from flask import Flask

from app.api.messages import routes as messages_routes


class TestStopMessageRoute:
    """The /messages/stop endpoint writes chats.user_stopped_at via
    chat_service. We call the route function directly inside a Flask test
    request context — the full app factory has a separate pytest-flask
    fixture issue (see test_auth_failopen.py)."""

    def _call_stop(self, project_id: str, chat_id: str):
        """Invoke stop_message inside a request context. Returns
        (response, status)."""
        app = Flask(__name__)
        with app.test_request_context(
            f"/api/v1/projects/{project_id}/chats/{chat_id}/messages/stop",
            method="POST",
        ):
            return messages_routes.stop_message(project_id, chat_id)

    def test_post_stop_writes_to_db_via_chat_service(self):
        with patch.object(
            messages_routes.chat_service, "mark_user_stopped", return_value=True,
        ) as mock_mark:
            resp, status = self._call_stop("proj-1", "chat-abc")
        mock_mark.assert_called_once_with("proj-1", "chat-abc")
        assert status == 200

    def test_post_stop_404s_when_chat_not_in_project(self):
        """mark_user_stopped returns False when the chat doesn't belong
        to the project (the SQL `.eq("project_id", X)` clause filters it
        out). This is the second-layer defence against cross-tenant
        stop-injection on top of the verify_project_access blueprint hook."""
        with patch.object(
            messages_routes.chat_service, "mark_user_stopped", return_value=False,
        ):
            resp, status = self._call_stop("proj-1", "chat-not-mine")
        assert status == 404

    def test_post_stop_uses_error_response_on_supabase_failure(self):
        """A blip in the chat_service write returns a typed error, not a
        bare str(e). Frontend toast will show the user-safe message
        instead of the internal exception text."""
        with patch.object(
            messages_routes.chat_service, "mark_user_stopped",
            side_effect=RuntimeError("supabase 500"),
        ), patch(
            "app.api.messages.routes.error_response",
        ) as mock_err:
            mock_err.return_value = ({"success": False}, 500)
            self._call_stop("proj-1", "chat-abc")
        mock_err.assert_called_once()


class TestGeneratorExitFreshness:
    """The freshness window is what closes the M1 race: a /stop POST that
    arrives AFTER the current message has already finished sets a
    user_stopped_at timestamp that's BEFORE the next stream's start
    wall-clock, so the next stream's GeneratorExit ignores it."""

    @staticmethod
    def _is_user_stop(stop_iso: str | None, stream_started: datetime) -> bool:
        """Mirror the freshness check in routes.py GeneratorExit."""
        if not stop_iso:
            return False
        try:
            stopped_at = datetime.fromisoformat(stop_iso.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False
        return stopped_at > stream_started

    def test_fresh_stop_during_stream_is_user_stop(self):
        started = datetime.now(timezone.utc) - timedelta(seconds=30)
        stopped = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        assert self._is_user_stop(stopped, started) is True

    def test_stale_stop_from_previous_message_is_ignored(self):
        """The M1 race regression test. A /stop POSTed yesterday must not
        retroactively mark today's stream as user-stopped."""
        started = datetime.now(timezone.utc) - timedelta(seconds=30)
        stopped = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert self._is_user_stop(stopped, started) is False

    def test_null_stop_column_is_not_user_stop(self):
        """Default state for any new chat. Must NOT trip the user-stop path."""
        started = datetime.now(timezone.utc)
        assert self._is_user_stop(None, started) is False

    def test_malformed_timestamp_is_conservative(self):
        """Unparseable values fall to the conservative default (not
        user-stop), matching the route-handler exception branch."""
        started = datetime.now(timezone.utc)
        assert self._is_user_stop("not-a-real-timestamp", started) is False

    def test_z_suffix_iso_format_parses(self):
        """Supabase returns timestamps with `+00:00` but other clients
        sometimes use `Z`. Both must parse cleanly."""
        started = datetime.now(timezone.utc) - timedelta(seconds=30)
        stopped_z = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat().replace(
            "+00:00", "Z"
        )
        assert self._is_user_stop(stopped_z, started) is True


class TestLabelingBranches:
    """main_chat_service writes one of three different message contents
    depending on (cancelled, user_stopped). Exercise the matrix in
    isolation — same shape as before H2."""

    @staticmethod
    def _label(cancelled: bool, user_stopped: bool, final_text: str) -> str:
        if cancelled and user_stopped:
            return (
                final_text + "\n\n_(stopped by user)_"
                if final_text.strip()
                else "_(stopped by user)_"
            )
        if cancelled:
            return final_text if final_text.strip() else "I've processed your request."
        return final_text or "I've processed your request."

    def test_user_stop_with_text_appends_marker(self):
        assert self._label(True, True, "partial answer") == \
            "partial answer\n\n_(stopped by user)_"

    def test_user_stop_with_empty_text_is_marker_only(self):
        assert self._label(True, True, "") == "_(stopped by user)_"

    def test_proxy_disconnect_with_text_persists_text_unchanged(self):
        """The new branch — was the false-positive case before §2.1."""
        assert self._label(True, False, "partial answer") == "partial answer"
        assert "stopped by user" not in self._label(True, False, "partial answer")

    def test_proxy_disconnect_with_empty_text_uses_placeholder(self):
        assert self._label(True, False, "") == "I've processed your request."

    def test_normal_completion_persists_text(self):
        assert self._label(False, False, "full answer") == "full answer"


class TestRequestIdValidation:
    """M2: malicious X-Request-Id must not slip through into log lines.
    Mirrors the regex in app/api/__init__.py."""

    def test_strict_alphanumeric_accepted(self):
        from app.api import _REQ_ID_RE
        assert _REQ_ID_RE.fullmatch("abc123") is not None
        assert _REQ_ID_RE.fullmatch("a1b2c3-d4e5_f6") is not None

    def test_log_injection_payload_rejected(self):
        from app.api import _REQ_ID_RE
        # The M2 review finding: `]` and `:` allowed by the previous
        # whitespace-only validation could break the log-parser regex.
        assert _REQ_ID_RE.fullmatch("abc]: spoofed-log [req:xyz") is None
        assert _REQ_ID_RE.fullmatch("abc]:fake") is None
        assert _REQ_ID_RE.fullmatch("abc def") is None
        assert _REQ_ID_RE.fullmatch("abc;dangerous") is None

    def test_too_long_rejected(self):
        from app.api import _REQ_ID_RE
        assert _REQ_ID_RE.fullmatch("a" * 65) is None
        assert _REQ_ID_RE.fullmatch("a" * 64) is not None  # exactly at the limit

    def test_empty_rejected(self):
        from app.api import _REQ_ID_RE
        assert _REQ_ID_RE.fullmatch("") is None
