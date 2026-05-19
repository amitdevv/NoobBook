"""
Log Housekeeping Scheduler — clears backend log files once a week.

Design:
- One daemon thread per process (matches `InsightScheduler`). The
  single-gunicorn-worker assumption holds: no cross-process coordination
  needed.
- Tick every 1 hour. Each tick reads `app_settings.log_housekeeping`:
    - If `weekly_clear_enabled = false` → no-op.
    - If `last_run_at` is null or older than 7 days → call
      `log_service.clear_logs("scheduler")` and bump `last_run_at`.
- Conditional UPDATE on `last_run_at` makes two racing ticks (which
  shouldn't happen with a single worker but might during a redeploy
  overlap) cheaply idempotent: the second update affects 0 rows and we
  skip the clear.
- Daemon thread dies with the worker. Tick failures are swallowed +
  logged so a transient Supabase blip can't take the app down.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.services.integrations.supabase import get_supabase, is_supabase_enabled
from app.services.log_service import clear_logs

logger = logging.getLogger(__name__)


# Hourly tick is plenty for a weekly cadence. Override via env for tests.
TICK_INTERVAL_SECONDS = int(os.getenv("LOG_HOUSEKEEPING_TICK_SECONDS", "3600"))
WEEKLY_INTERVAL = timedelta(days=7)
STARTUP_DELAY_SECONDS = 60


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Accept both `...Z` and `+00:00` forms.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _read_housekeeping_row() -> Optional[Dict[str, Any]]:
    """Return the single `app_settings` row's log_housekeeping JSONB, or None."""
    if not is_supabase_enabled():
        return None
    try:
        client = get_supabase()
        resp = (
            client.table("app_settings")
            .select("log_housekeeping")
            .eq("id", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning("log housekeeping: could not read app_settings: %s", exc)
        return None
    rows = resp.data or []
    if not rows:
        return None
    return rows[0].get("log_housekeeping") or {}


def _try_update_last_run(
    previous_last_run: Optional[str],
    new_value: str,
    weekly_enabled: bool,
) -> bool:
    """
    Bump `last_run_at` only if it still matches what we read at the top of
    the tick. Returns True if our row was the one we updated (we own this
    clear), False otherwise (another tick beat us to it).

    `weekly_enabled` is the value we observed at the top of the tick. We
    write it back verbatim AND gate the UPDATE on the same value so a
    concurrent admin "disable" between our read and our write wins the
    race — our update affects 0 rows and the scheduler skips the clear,
    preserving the admin's intent. The earlier implementation hardcoded
    `weekly_clear_enabled=True` here, which silently re-enabled the
    toggle whenever the admin flipped it off mid-tick.
    """
    if not is_supabase_enabled():
        return False
    try:
        client = get_supabase()
        query = client.table("app_settings").update(
            {
                "log_housekeeping": {
                    "weekly_clear_enabled": weekly_enabled,
                    "last_run_at": new_value,
                }
            }
        ).eq("id", True)
        if previous_last_run is None:
            query = query.is_("log_housekeeping->>last_run_at", "null")
        else:
            query = query.eq("log_housekeeping->>last_run_at", previous_last_run)
        query = query.eq(
            "log_housekeeping->>weekly_clear_enabled",
            "true" if weekly_enabled else "false",
        )
        resp = query.execute()
        return bool(resp.data)
    except Exception as exc:
        logger.warning("log housekeeping: could not update last_run_at: %s", exc)
        return False


def _merge_full_row(weekly_enabled: bool, last_run_at: Optional[str]) -> Dict[str, Any]:
    """Helper kept for tests — full-row update payload preserving toggle state."""
    return {
        "weekly_clear_enabled": weekly_enabled,
        "last_run_at": last_run_at,
    }


class LogHousekeepingScheduler:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._run,
            name="log-housekeeping",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Log housekeeping scheduler started (tick=%ss, weekly clear)",
            TICK_INTERVAL_SECONDS,
        )

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        if self._stop.wait(STARTUP_DELAY_SECONDS):
            return
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Log housekeeping tick failed: %s", exc)
            if self._stop.wait(TICK_INTERVAL_SECONDS):
                break

    def tick(self) -> Dict[str, Any]:
        """
        One scheduler iteration. Public so tests (and an /admin trigger
        endpoint, if we ever add one) can call it directly. Returns a
        small status dict.
        """
        config = _read_housekeeping_row()
        if config is None:
            return {"ran": False, "reason": "no app_settings row"}
        weekly_enabled = bool(config.get("weekly_clear_enabled", True))
        if not weekly_enabled:
            return {"ran": False, "reason": "weekly_clear_enabled=false"}

        last_run_raw = config.get("last_run_at")
        last_run = _parse_iso(last_run_raw)
        now = _now_utc()
        if last_run is not None and now - last_run < WEEKLY_INTERVAL:
            return {"ran": False, "reason": "not yet due", "last_run_at": last_run_raw}

        new_value = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Pass the observed weekly_enabled through so the UPDATE
        # preserves it and the conditional WHERE picks up any admin
        # disable that landed between our read and our write.
        if not _try_update_last_run(last_run_raw, new_value, weekly_enabled):
            # Another tick (or admin) bumped it first. Skip the clear so
            # we don't double-wipe.
            return {"ran": False, "reason": "lost race"}

        result = clear_logs(initiator="scheduler")
        return {
            "ran": True,
            "cleared": result.get("cleared", 0),
            "last_run_at": new_value,
        }


log_housekeeping_scheduler = LogHousekeepingScheduler()
