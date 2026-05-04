"""
Standardized spending-period reset schedule.

Background: each user's `period_start` used to be set to the moment
they were created (or admin-reset). That meant one user's "weekly"
reset rolled over Wednesday 3:42 PM, another's Friday 11:17 PM —
inconsistent, hard to support ("when does mine reset?" had a different
answer per user). Users complained that their credits weren't
resetting, when in fact they reset *lazily* on their next request
*if* the period had elapsed since their personal start time.

This module aligns every user to a single anchor moment per period
type, computed in a configured timezone and stored in UTC. All weekly
users now reset at the same wall-clock instant (default: Sunday
09:00 Asia/Kolkata).

Env knobs (read once at module load):
  NOOBBOOK_RESET_TZ           — IANA tz name (default 'Asia/Kolkata')
  NOOBBOOK_RESET_HOUR         — 0..23 (default 9)
  NOOBBOOK_RESET_WEEKLY_DAY   — Python weekday(): Mon=0..Sun=6
                                 (default 6 = Sunday)
  NOOBBOOK_RESET_MONTHLY_DAY  — day-of-month 1..28 (default 1; capped
                                 to 28 to dodge Feb edge-cases)

Notes on the design:
  • Lazy reset preserved — we DO NOT add a cron worker. The existing
    `check_user_spending_limit` flow already runs on every API request
    and resets when it sees the boundary has passed. The only change
    is *which* boundary we compute.
  • Admin manual reset zeroes period_spend AND aligns period_start to
    the most recent anchor — so the user's next auto-reset still
    happens at the same anchor moment as everyone else.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Python's weekday() returns Monday=0..Sunday=6 — used by NOOBBOOK_RESET_WEEKLY_DAY.
_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _load_anchor() -> Dict[str, Any]:
    """Read env vars once. Falls back loudly on invalid values."""
    tz_name = os.getenv("NOOBBOOK_RESET_TZ", "Asia/Kolkata")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        logger.warning(
            "Invalid NOOBBOOK_RESET_TZ=%r; falling back to Asia/Kolkata", tz_name
        )
        tz_name = "Asia/Kolkata"
        tz = ZoneInfo(tz_name)

    def _read_int(name: str, default: int, lo: int, hi: int) -> int:
        raw = os.getenv(name, str(default))
        try:
            value = int(raw)
            if not lo <= value <= hi:
                raise ValueError(f"{name}={value} out of [{lo},{hi}]")
            return value
        except ValueError as exc:
            logger.warning("Invalid %s=%r (%s); falling back to %d", name, raw, exc, default)
            return default

    return {
        "tz": tz,
        "tz_name": tz_name,
        "hour": _read_int("NOOBBOOK_RESET_HOUR", 9, 0, 23),
        "weekday": _read_int("NOOBBOOK_RESET_WEEKLY_DAY", 6, 0, 6),
        "monthly_day": _read_int("NOOBBOOK_RESET_MONTHLY_DAY", 1, 1, 28),
    }


_ANCHOR = _load_anchor()


def get_anchor_summary() -> Dict[str, Any]:
    """Human-readable summary of the current anchor — surfaced to the
    admin UI so operators can see exactly when resets fire."""
    return {
        "tz": _ANCHOR["tz_name"],
        "hour": _ANCHOR["hour"],
        "weekday": _ANCHOR["weekday"],
        "weekday_name": _WEEKDAY_NAMES[_ANCHOR["weekday"]],
        "monthly_day": _ANCHOR["monthly_day"],
        "weekly_label": (
            f"Every {_WEEKDAY_NAMES[_ANCHOR['weekday']]} "
            f"at {_ANCHOR['hour']:02d}:00 {_ANCHOR['tz_name']}"
        ),
        "daily_label": f"Every day at {_ANCHOR['hour']:02d}:00 {_ANCHOR['tz_name']}",
        "monthly_label": (
            f"Day {_ANCHOR['monthly_day']} of every month "
            f"at {_ANCHOR['hour']:02d}:00 {_ANCHOR['tz_name']}"
        ),
    }


def _to_iso_z(dt: datetime) -> str:
    """Convert any datetime to UTC ISO-8601 with `Z` suffix.
    Matches the storage convention in users.settings.period_start."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _from_iso(value: str) -> datetime:
    """Parse our ISO-8601-with-Z storage format back to a tz-aware UTC dt."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def compute_period_start(now: datetime, frequency: str) -> datetime:
    """
    Find the most recent anchor boundary at or before `now`.
    Returns a tz-aware datetime in the configured anchor TZ. The caller
    typically converts to UTC via `_to_iso_z` for storage.
    """
    anchor = _ANCHOR
    now_local = now.astimezone(anchor["tz"])

    if frequency == "daily":
        candidate = now_local.replace(
            hour=anchor["hour"], minute=0, second=0, microsecond=0
        )
        if candidate > now_local:
            candidate -= timedelta(days=1)
        return candidate

    if frequency == "weekly":
        candidate = now_local.replace(
            hour=anchor["hour"], minute=0, second=0, microsecond=0
        )
        # Python weekday(): Mon=0..Sun=6. Walk back to the most recent
        # occurrence of `anchor["weekday"]`.
        days_back = (candidate.weekday() - anchor["weekday"]) % 7
        candidate -= timedelta(days=days_back)
        # If today IS the anchor weekday but the anchor hour hasn't passed
        # yet, the previous anchor was 7 days ago.
        if candidate > now_local:
            candidate -= timedelta(days=7)
        return candidate

    if frequency == "monthly":
        candidate = now_local.replace(
            day=anchor["monthly_day"],
            hour=anchor["hour"],
            minute=0,
            second=0,
            microsecond=0,
        )
        if candidate > now_local:
            # Walk back one month
            year = candidate.year
            month = candidate.month - 1
            if month == 0:
                month = 12
                year -= 1
            candidate = candidate.replace(year=year, month=month)
        return candidate

    # Unknown frequency — return now as-is so callers don't crash.
    return now_local


def compute_next_reset(period_start: datetime, frequency: str) -> datetime:
    """When does the next reset fire, given a period_start? Used for
    UI 'next reset' hints and the auto-reset boundary check."""
    anchor = _ANCHOR
    start_local = period_start.astimezone(anchor["tz"])

    if frequency == "daily":
        return start_local + timedelta(days=1)
    if frequency == "weekly":
        return start_local + timedelta(days=7)
    if frequency == "monthly":
        # +1 calendar month, same day-of-month / hour.
        year = start_local.year + (1 if start_local.month == 12 else 0)
        month = 1 if start_local.month == 12 else start_local.month + 1
        try:
            return start_local.replace(year=year, month=month)
        except ValueError:
            # Should never hit this since monthly_day is capped at 28.
            return start_local + timedelta(days=30)
    return start_local


def is_period_expired(
    period_start_iso: Optional[str], frequency: Optional[str]
) -> bool:
    """True if the period boundary has passed and an auto-reset is due."""
    if not period_start_iso or not frequency:
        return False
    try:
        period_start = _from_iso(period_start_iso)
        now = datetime.now(timezone.utc)
        return now >= compute_next_reset(period_start, frequency)
    except Exception as exc:
        logger.warning("Failed to evaluate period expiry: %s", exc)
        return False


def aligned_period_start_iso(frequency: str) -> str:
    """Most recent anchor boundary at-or-before now, as UTC ISO-8601 + Z.
    Used when seeding new users, on admin reset, and during the bulk
    realign endpoint."""
    now_anchor_tz = datetime.now(_ANCHOR["tz"])
    return _to_iso_z(compute_period_start(now_anchor_tz, frequency))


def next_reset_iso(
    period_start_iso: Optional[str], frequency: Optional[str]
) -> Optional[str]:
    """Compute when this period will next auto-reset, for UI display."""
    if not period_start_iso or not frequency:
        return None
    try:
        period_start = _from_iso(period_start_iso)
        return _to_iso_z(compute_next_reset(period_start, frequency))
    except Exception:
        return None
