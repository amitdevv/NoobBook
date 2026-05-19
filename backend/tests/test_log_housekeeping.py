"""
Tests for the log download / housekeeping feature:
- user_service.set_settings_key merges into the existing settings JSONB.
- log_service.clear_logs truncates the active file and removes archives.
- LogHousekeepingScheduler.tick is idempotent within the 7-day window and
  respects the weekly_clear_enabled flag.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

# Importing the user_service module pulls in supabase auth; provide
# safe placeholders before app imports (mirrors test_notion_source.py).
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoidGVzdCJ9.test",
)

import importlib

import pytest


# ---------------------------------------------------------------------------
# user_service.set_settings_key
# ---------------------------------------------------------------------------


def test_set_settings_key_merges_preserving_other_keys(monkeypatch):
    user_module = importlib.import_module(
        "app.services.data_services.user_service"
    )

    svc = user_module.UserService.__new__(user_module.UserService)
    svc.table = "users"
    svc.supabase = MagicMock()

    # Existing settings already hold a spending-config field; we must NOT lose it.
    monkeypatch.setattr(
        svc,
        "get_user_settings_raw",
        lambda user_id: {"cost_limit": 25.0, "reset_frequency": "weekly"},
    )

    captured = {}

    def fake_save(user_id, settings):
        captured["user_id"] = user_id
        captured["settings"] = settings
        return True

    monkeypatch.setattr(svc, "save_user_settings", fake_save)

    ok = svc.set_settings_key("u1", "auto_delete_logs_on_download", True)
    assert ok is True
    assert captured["user_id"] == "u1"
    assert captured["settings"] == {
        "cost_limit": 25.0,
        "reset_frequency": "weekly",
        "auto_delete_logs_on_download": True,
    }


def test_set_settings_key_noop_when_unchanged(monkeypatch):
    user_module = importlib.import_module(
        "app.services.data_services.user_service"
    )
    svc = user_module.UserService.__new__(user_module.UserService)
    svc.table = "users"
    svc.supabase = MagicMock()

    monkeypatch.setattr(
        svc,
        "get_user_settings_raw",
        lambda user_id: {"auto_delete_logs_on_download": True},
    )
    # save_user_settings must not be called for an idempotent toggle.
    called = {"n": 0}

    def fake_save(user_id, settings):
        called["n"] += 1
        return True

    monkeypatch.setattr(svc, "save_user_settings", fake_save)

    assert svc.set_settings_key("u1", "auto_delete_logs_on_download", True) is True
    assert called["n"] == 0


# ---------------------------------------------------------------------------
# log_service.clear_logs
# ---------------------------------------------------------------------------


def test_clear_logs_truncates_and_removes_archives(tmp_path, monkeypatch):
    log_module = importlib.import_module("app.utils.logger")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    active = log_dir / "backend.log"
    active.write_text("hello world", encoding="utf-8")
    (log_dir / "backend.log.1").write_text("archive1", encoding="utf-8")
    (log_dir / "backend.log.2").write_text("archive2", encoding="utf-8")

    monkeypatch.setattr(log_module, "LOG_DIR", log_dir)
    monkeypatch.setattr(log_module, "LOG_FILE", active)

    log_service = importlib.import_module("app.services.log_service")
    result = log_service.clear_logs(initiator="pytest")
    assert result["success"] is True
    assert result["cleared"] == 3
    assert active.read_text() == ""
    assert not (log_dir / "backend.log.1").exists()
    assert not (log_dir / "backend.log.2").exists()


def test_clear_logs_handles_missing_log_file(monkeypatch):
    log_module = importlib.import_module("app.utils.logger")
    monkeypatch.setattr(log_module, "LOG_FILE", None)
    log_service = importlib.import_module("app.services.log_service")
    result = log_service.clear_logs(initiator="pytest")
    assert result == {"success": True, "cleared": 0, "message": "no log file"}


# ---------------------------------------------------------------------------
# LogHousekeepingScheduler.tick
# ---------------------------------------------------------------------------


def _import_scheduler():
    return importlib.import_module(
        "app.services.background_services.log_housekeeping_scheduler"
    )


def test_tick_no_op_when_weekly_disabled(monkeypatch):
    sched = _import_scheduler()
    monkeypatch.setattr(
        sched, "_read_housekeeping_row",
        lambda: {"weekly_clear_enabled": False, "last_run_at": None},
    )
    cleared = {"called": False}
    monkeypatch.setattr(sched, "clear_logs", lambda **kw: cleared.update(called=True) or {"success": True})

    result = sched.LogHousekeepingScheduler().tick()
    assert result["ran"] is False
    assert result["reason"] == "weekly_clear_enabled=false"
    assert cleared["called"] is False


def test_tick_runs_when_never_run_before(monkeypatch):
    sched = _import_scheduler()
    monkeypatch.setattr(
        sched, "_read_housekeeping_row",
        lambda: {"weekly_clear_enabled": True, "last_run_at": None},
    )
    monkeypatch.setattr(sched, "_try_update_last_run", lambda prev, new: True)
    called = {"n": 0}

    def fake_clear(initiator="?"):
        called["n"] += 1
        return {"success": True, "cleared": 4}

    monkeypatch.setattr(sched, "clear_logs", fake_clear)

    result = sched.LogHousekeepingScheduler().tick()
    assert result["ran"] is True
    assert result["cleared"] == 4
    assert called["n"] == 1


def test_tick_idempotent_within_week(monkeypatch):
    sched = _import_scheduler()
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(
        sched, "_read_housekeeping_row",
        lambda: {"weekly_clear_enabled": True, "last_run_at": recent},
    )
    called = {"n": 0}
    monkeypatch.setattr(sched, "clear_logs", lambda **kw: called.update(n=called["n"] + 1) or {"success": True})

    result = sched.LogHousekeepingScheduler().tick()
    assert result["ran"] is False
    assert result["reason"] == "not yet due"
    assert called["n"] == 0


def test_tick_runs_when_older_than_seven_days(monkeypatch):
    sched = _import_scheduler()
    stale = (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(
        sched, "_read_housekeeping_row",
        lambda: {"weekly_clear_enabled": True, "last_run_at": stale},
    )
    monkeypatch.setattr(sched, "_try_update_last_run", lambda prev, new: True)
    called = {"n": 0}
    monkeypatch.setattr(sched, "clear_logs", lambda **kw: called.update(n=called["n"] + 1) or {"success": True, "cleared": 2})

    result = sched.LogHousekeepingScheduler().tick()
    assert result["ran"] is True
    assert called["n"] == 1


def test_tick_skips_when_update_race_lost(monkeypatch):
    """If another worker bumps last_run_at between read and write, we must
    not double-clear."""
    sched = _import_scheduler()
    monkeypatch.setattr(
        sched, "_read_housekeeping_row",
        lambda: {"weekly_clear_enabled": True, "last_run_at": None},
    )
    monkeypatch.setattr(sched, "_try_update_last_run", lambda prev, new: False)
    called = {"n": 0}
    monkeypatch.setattr(sched, "clear_logs", lambda **kw: called.update(n=called["n"] + 1) or {"success": True})

    result = sched.LogHousekeepingScheduler().tick()
    assert result["ran"] is False
    assert result["reason"] == "lost race"
    assert called["n"] == 0


def test_tick_returns_no_config_when_row_missing(monkeypatch):
    sched = _import_scheduler()
    monkeypatch.setattr(sched, "_read_housekeeping_row", lambda: None)
    result = sched.LogHousekeepingScheduler().tick()
    assert result == {"ran": False, "reason": "no app_settings row"}
