"""
User Service - Admin-oriented user management (roles, create, delete).

Note: This service uses a dedicated Supabase client for admin operations.
The shared singleton client gets user sessions set on it during sign-in,
which causes auth.admin methods to use the user's token instead of the
service_role key. By creating a separate client here, we ensure admin
operations always use the service_role key.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from supabase import create_client

from app.services.integrations.supabase import is_supabase_enabled
from app.utils.password_utils import generate_secure_password

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """ISO-8601 UTC with `Z` suffix — matches the convention used elsewhere
    in this module (see `update_spending_config`)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SpendingPersistenceError(RuntimeError):
    """Raised when a spending-config write succeeds at the SDK level but
    Supabase reports zero rows affected (e.g. the user_id was deleted
    between fetch and update). Distinct from the "user has no cost_limit
    to reset" case so the route layer can map each to the correct HTTP
    status — 500 vs 400.
    """


def default_user_settings() -> Dict[str, Any]:
    """
    Build the seed `users.settings` JSONB for newly-created accounts.

    Driven by env vars so self-hosted operators can override without a
    code change:
      - NOOBBOOK_DEFAULT_USER_COST_LIMIT  (default: 25)
      - NOOBBOOK_DEFAULT_USER_RESET_FREQUENCY  (default: weekly)

    Setting the limit to 0 (or any non-positive number) opts out — new
    users get an empty settings object and behave as unlimited, matching
    the pre-feature default.
    """
    raw_limit = os.getenv("NOOBBOOK_DEFAULT_USER_COST_LIMIT", "25")
    raw_freq = os.getenv("NOOBBOOK_DEFAULT_USER_RESET_FREQUENCY", "weekly")

    try:
        cost_limit = float(raw_limit)
    except ValueError:
        logger.warning(
            "Invalid NOOBBOOK_DEFAULT_USER_COST_LIMIT=%r; falling back to 25", raw_limit
        )
        cost_limit = 25.0

    if cost_limit <= 0:
        return {}

    if raw_freq not in ("daily", "weekly", "monthly", "none"):
        logger.warning(
            "Invalid NOOBBOOK_DEFAULT_USER_RESET_FREQUENCY=%r; falling back to weekly",
            raw_freq,
        )
        raw_freq = "weekly"

    if raw_freq == "none":
        return {"cost_limit": cost_limit, "period_spend": 0.0}

    # Anchor period_start to the standardized schedule (default Sunday
    # 09:00 Asia/Kolkata) so every new user joins the same global reset
    # cadence as everyone else — no per-user drift.
    from app.utils.spending_schedule import aligned_period_start_iso

    return {
        "cost_limit": cost_limit,
        "reset_frequency": raw_freq,
        "period_spend": 0.0,
        "period_start": aligned_period_start_iso(raw_freq),
    }


class UserService:
    def __init__(self) -> None:
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        # Create a dedicated client for admin operations to avoid session contamination
        # from user logins on the shared singleton client
        supabase_url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url:
            raise RuntimeError(
                "SUPABASE_URL is required for admin user management. "
                "Please add it to your .env file."
            )
        if not service_key:
            raise RuntimeError(
                "SUPABASE_SERVICE_KEY is required for admin user management. "
                "Please add it to your .env file."
            )
        self.supabase = create_client(supabase_url, service_key)
        self.table = "users"

    def list_users(self) -> List[Dict[str, str]]:
        resp = (
            self.supabase.table(self.table)
            .select("id, email, role, settings, created_at, updated_at")
            .order("created_at", desc=False)
            .execute()
        )
        users = resp.data or []
        # Surface spending fields from settings JSONB for the frontend table
        for user in users:
            settings = user.pop("settings", None) or {}
            settings = self.maybe_reset_expired_spending_period(user["id"], settings)
            user["cost_limit"] = settings.get("cost_limit")
            user["reset_frequency"] = settings.get("reset_frequency")  # daily/weekly/monthly/null
            user["period_spend"] = settings.get("period_spend", 0.0)
            user["period_start"] = settings.get("period_start")
        return users

    def search_users_by_email(
        self,
        prefix: str,
        limit: int = 10,
        exclude_user_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Find users whose email starts with `prefix` (case-insensitive).

        Used by the share-modal autocomplete: only the prefix (not arbitrary
        substring) so a typo doesn't surface unrelated accounts, and so
        results are predictable for type-ahead.
        """
        prefix = (prefix or "").strip().lower()
        if len(prefix) < 1:
            return []

        # Cap limit so a malformed client can't flood the response.
        capped_limit = max(1, min(limit, 25))

        # `ilike` with a trailing % gives us case-insensitive prefix match.
        # Escape any % / _ the caller embedded so they're treated literally.
        safe = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = (
            self.supabase.table(self.table)
            .select("id, email")
            .ilike("email", f"{safe}%")
            .order("email", desc=False)
            .limit(capped_limit)
        )
        if exclude_user_id:
            query = query.neq("id", exclude_user_id)
        resp = query.execute()
        return resp.data or []

    def get_user(self, user_id: str) -> Optional[Dict[str, str]]:
        resp = (
            self.supabase.table(self.table)
            .select("id, email, role, settings, created_at, updated_at")
            .eq("id", user_id)
            .execute()
        )
        if resp.data:
            user = resp.data[0]
            settings = user.pop("settings", None) or {}
            settings = self.maybe_reset_expired_spending_period(user_id, settings)
            user["cost_limit"] = settings.get("cost_limit")
            user["reset_frequency"] = settings.get("reset_frequency")
            user["period_spend"] = settings.get("period_spend", 0.0)
            user["period_start"] = settings.get("period_start")
            return user
        return None

    def get_user_settings_raw(self, user_id: str) -> Dict[str, Any]:
        """Read the raw settings JSONB for a user."""
        resp = (
            self.supabase.table(self.table)
            .select("settings")
            .eq("id", user_id)
            .execute()
        )
        if not resp.data:
            return {}
        return resp.data[0].get("settings") or {}

    def save_user_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Write the full settings JSONB for a user."""
        resp = (
            self.supabase.table(self.table)
            .update({"settings": settings})
            .eq("id", user_id)
            .execute()
        )
        return bool(resp.data)

    def maybe_reset_expired_spending_period(
        self,
        user_id: str,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Reset a user's period spend if their configured window has expired.

        The reset is intentionally lazy, but this method is called from both
        reads and writes so stale weekly/monthly spend does not linger until a
        specific Claude code path happens to run.
        """
        current = dict(settings if settings is not None else self.get_user_settings_raw(user_id))
        if not current.get("cost_limit") or not current.get("reset_frequency"):
            return current

        reset_frequency = current["reset_frequency"]
        period_start = current.get("period_start")

        from app.utils.spending_schedule import (
            aligned_period_start_iso,
            is_period_expired,
        )

        should_reset = not period_start or is_period_expired(period_start, reset_frequency)
        if not should_reset:
            return current

        next_settings = {
            **current,
            "period_spend": 0.0,
            "period_start": aligned_period_start_iso(reset_frequency),
        }
        if self.save_user_settings(user_id, next_settings):
            logger.info(
                "Reset expired %s spending period for user %s",
                reset_frequency,
                user_id,
            )
            return next_settings

        logger.warning("Failed to persist expired spending-period reset for %s", user_id)
        return next_settings

    def update_spending_config(
        self,
        user_id: str,
        cost_limit: Optional[float] = None,
        reset_frequency: Optional[str] = None,
    ) -> bool:
        """
        Update a user's spending limit and reset frequency.

        Educational Note: Stored in users.settings JSONB.
        - cost_limit: Max USD per period (null = unlimited)
        - reset_frequency: "daily" | "weekly" | "monthly" | null (null = lifetime/no reset)
        - When reset_frequency changes, period_spend resets to 0 with a new period_start
        """
        settings = self.get_user_settings_raw(user_id)
        if settings is None:
            return False

        old_freq = settings.get("reset_frequency")

        # Update limit
        if cost_limit is not None and cost_limit > 0:
            settings["cost_limit"] = cost_limit
        elif cost_limit is None or cost_limit == 0:
            settings.pop("cost_limit", None)
            settings.pop("reset_frequency", None)
            settings.pop("period_spend", None)
            settings.pop("period_start", None)
            return self.save_user_settings(user_id, settings)

        # Update reset frequency
        if reset_frequency in ("daily", "weekly", "monthly"):
            settings["reset_frequency"] = reset_frequency
            # Reset period if frequency changed. Anchor to the global
            # schedule (default Sunday 09:00 Asia/Kolkata) so this user
            # joins the same reset cadence as everyone else.
            if reset_frequency != old_freq:
                from app.utils.spending_schedule import aligned_period_start_iso

                settings["period_spend"] = 0.0
                settings["period_start"] = aligned_period_start_iso(reset_frequency)
        else:
            settings.pop("reset_frequency", None)
            settings.pop("period_spend", None)
            settings.pop("period_start", None)

        return self.save_user_settings(user_id, settings)

    def reset_spending_period(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Hard-reset a user's period_spend to 0 and bump period_start to now.

        Used by the admin "Reset spend now" button — lets an operator clear
        a user's running tally without waiting for the time-based weekly /
        monthly tick. For lifetime caps (no `reset_frequency`), zeroes
        period_spend only and leaves period_start untouched.

        Returns:
            Updated settings dict on success.
            None if the user has no `cost_limit` set (nothing to reset).
            Caller surfaces this as a 400.

        Raises:
            SpendingPersistenceError: if the underlying Supabase write
            reports zero rows affected. Caller surfaces as a 500 — this
            is a real backend failure, not a "no-op" the admin can
            interpret as "user already had no limit".
            Missing-user is handled at the route layer via a pre-fetch
            `get_user`.
        """
        settings = self.get_user_settings_raw(user_id)
        if not settings.get("cost_limit"):
            return None

        settings["period_spend"] = 0.0
        if settings.get("reset_frequency"):
            # Anchor to the standardized schedule, NOT to `now`. Two
            # reasons: (1) the user's next auto-reset still happens at
            # the same wall-clock instant as everyone else (Sunday
            # 09:00 IST by default), so admins don't accidentally
            # offset a user's reset cadence by clicking the button;
            # (2) keeps support answers uniform — "your reset is
            # always Sunday 9am IST" regardless of admin actions.
            from app.utils.spending_schedule import aligned_period_start_iso

            settings["period_start"] = aligned_period_start_iso(
                settings["reset_frequency"]
            )

        if not self.save_user_settings(user_id, settings):
            raise SpendingPersistenceError(
                f"Supabase update affected 0 rows for user {user_id}"
            )
        return settings

    def count_unlimited_users(self) -> int:
        """Number of users with no `cost_limit` set in their settings.

        Used by the admin Team table to decide whether to surface the
        "Apply default to unlimited users" banner. Reads `settings` only
        — cheap.
        """
        resp = self.supabase.table(self.table).select("settings").execute()
        rows = resp.data or []
        return sum(
            1 for r in rows
            if not (r.get("settings") or {}).get("cost_limit")
        )

    def apply_default_to_unlimited_users(self) -> Dict[str, Any]:
        """
        Apply the env-configured default spending limit to every user
        whose `settings.cost_limit` is currently unset.

        Existing users with a limit (any value) are skipped — the admin
        explicitly intended their config and we don't want to overwrite
        it. New users created after this call still pick up the same
        defaults via the standard creation paths.

        Returns:
            Dict with `updated`, `skipped`, `default_limit`,
            `default_frequency`, and `opted_out` (true when the env
            override sets the limit to 0 / non-positive — in that case
            no work is done and the caller should surface it).
        """
        defaults = default_user_settings()
        if not defaults.get("cost_limit"):
            return {
                "updated": 0,
                "skipped": 0,
                "default_limit": None,
                "default_frequency": None,
                "opted_out": True,
            }

        resp = (
            self.supabase.table(self.table)
            .select("id, settings")
            .execute()
        )
        rows = resp.data or []

        updated = 0
        skipped = 0
        for row in rows:
            current = row.get("settings") or {}
            if current.get("cost_limit"):
                skipped += 1
                continue
            # Merge defaults INTO the existing settings so any unrelated
            # keys (memory hints, future extensions) survive the bulk
            # update.
            merged = {**current, **defaults}
            if self.save_user_settings(row["id"], merged):
                updated += 1

        return {
            "updated": updated,
            "skipped": skipped,
            "default_limit": defaults.get("cost_limit"),
            "default_frequency": defaults.get("reset_frequency"),
            "opted_out": False,
        }

    def count_users_with_reset_frequency(self) -> int:
        """How many users currently have a `reset_frequency` set.
        Drives the admin "Realign now" surface — only meaningful when
        there are users to realign."""
        resp = self.supabase.table(self.table).select("settings").execute()
        rows = resp.data or []
        return sum(
            1 for r in rows
            if (r.get("settings") or {}).get("reset_frequency")
        )

    def realign_spending_periods(self) -> Dict[str, Any]:
        """
        Bulk-realign every user with a `reset_frequency` to the
        standardized anchor schedule. Zeroes their `period_spend` (the
        "full reset" semantic the operator opted into when this feature
        shipped) and rewrites `period_start` to the most recent anchor
        boundary.

        Idempotent: running twice in a row produces the same result.
        Users without a `reset_frequency` are untouched.

        Returns dict with `updated`, `skipped`, plus the anchor summary
        the caller surfaces in the audit log + UI confirmation toast.
        """
        from app.utils.spending_schedule import (
            aligned_period_start_iso,
            get_anchor_summary,
        )

        resp = (
            self.supabase.table(self.table)
            .select("id, settings")
            .execute()
        )
        rows = resp.data or []

        updated = 0
        skipped = 0
        for row in rows:
            current = row.get("settings") or {}
            frequency = current.get("reset_frequency")
            if not frequency or not current.get("cost_limit"):
                skipped += 1
                continue
            new_settings = {
                **current,
                "period_spend": 0.0,
                "period_start": aligned_period_start_iso(frequency),
            }
            if self.save_user_settings(row["id"], new_settings):
                updated += 1

        return {
            "updated": updated,
            "skipped": skipped,
            "anchor": get_anchor_summary(),
        }

    def increment_period_spend(self, user_id: str, amount: float) -> None:
        """
        Add to the user's period_spend after a successful API call.

        Educational Note: Called from cost_tracking.add_usage() alongside
        project and chat cost updates. Only increments if the user has
        a cost_limit with a reset_frequency configured.
        """
        settings = self.maybe_reset_expired_spending_period(user_id)
        if not settings.get("cost_limit") or not settings.get("reset_frequency"):
            return  # No period tracking configured

        settings["period_spend"] = settings.get("period_spend", 0.0) + amount
        self.save_user_settings(user_id, settings)

    def get_user_total_spend(self, user_id: str) -> float:
        """
        Sum total_cost across all projects owned by this user.

        Educational Note: Each project stores a costs JSONB with total_cost.
        We aggregate across all projects to get the user's total spend.
        """
        from app.services.integrations.supabase import get_supabase
        client = get_supabase()
        resp = (
            client.table("projects")
            .select("costs")
            .eq("user_id", user_id)
            .execute()
        )
        total = 0.0
        for project in (resp.data or []):
            costs = project.get("costs") or {}
            total += costs.get("total_cost", 0.0)
        return total

    def get_usage_summary(self, user_id: str) -> Optional[Dict[str, Any]]:
        user = self.get_user(user_id)
        if not user:
            return None

        cost_limit = user.get("cost_limit")
        reset_frequency = user.get("reset_frequency")
        period_spend = user.get("period_spend", 0.0)
        period_start = user.get("period_start")
        total_spend = self.get_user_total_spend(user_id)

        if reset_frequency and cost_limit:
            current_spend = period_spend
        elif cost_limit:
            current_spend = total_spend
        else:
            current_spend = total_spend

        usage_pct = (current_spend / cost_limit * 100) if cost_limit and cost_limit > 0 else 0

        return {
            "cost_limit": cost_limit,
            "reset_frequency": reset_frequency,
            "current_spend": current_spend,
            "total_spend": total_spend,
            "period_start": period_start,
            "usage_percent": usage_pct,
            "snapshot_at": datetime.utcnow().isoformat() + "Z",
        }

    def count_admins(self) -> int:
        resp = (
            self.supabase.table(self.table)
            .select("id")
            .eq("role", "admin")
            .execute()
        )
        return len(resp.data or [])

    def update_role(self, user_id: str, role: str) -> Optional[Dict[str, str]]:
        if role not in {"admin", "user"}:
            raise ValueError("role must be 'admin' or 'user'")

        existing = self.get_user(user_id)
        if not existing:
            return None

        if existing.get("role") == "admin" and role == "user":
            if self.count_admins() <= 1:
                raise ValueError("Cannot remove the last admin user")

        resp = (
            self.supabase.table(self.table)
            .update({"role": role})
            .eq("id", user_id)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return self.get_user(user_id)

    def create_user(self, email: str, role: str = "user") -> Tuple[Dict, str]:
        """
        Create a new user with a generated password.

        Args:
            email: User's email address
            role: User role ('admin' or 'user', default 'user')

        Returns:
            Tuple of (user_dict, plain_password)

        Raises:
            ValueError: If email is invalid or already exists
        """
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("Invalid email address")

        if role not in {"admin", "user"}:
            raise ValueError("role must be 'admin' or 'user'")

        # Check if user already exists
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("email", email)
            .execute()
        )
        if existing.data:
            raise ValueError("A user with this email already exists")

        # Generate secure password
        password = generate_secure_password()

        # Create user in Supabase Auth
        response = self.supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True
        })

        auth_user = getattr(response, "user", None) or response
        user_id = getattr(auth_user, "id", None)

        if not user_id:
            raise ValueError("Failed to create user in auth system")

        # Create profile in public.users with the env-driven default
        # spending limit ($25/week unless an operator overrides via
        # NOOBBOOK_DEFAULT_USER_COST_LIMIT / RESET_FREQUENCY).
        self.supabase.table(self.table).insert({
            "id": user_id,
            "email": email,
            "role": role,
            "memory": {},
            "settings": default_user_settings()
        }).execute()

        user = self.get_user(user_id)
        return user, password

    def delete_user(self, user_id: str, requesting_user_id: str) -> bool:
        """
        Delete a user.

        Args:
            user_id: ID of user to delete
            requesting_user_id: ID of admin making the request

        Returns:
            True if deletion was successful

        Raises:
            ValueError: If trying to delete self or last admin
        """
        if user_id == requesting_user_id:
            raise ValueError("Cannot delete yourself")

        existing = self.get_user(user_id)
        if not existing:
            raise ValueError("User not found")

        # Check if deleting last admin
        if existing.get("role") == "admin":
            if self.count_admins() <= 1:
                raise ValueError("Cannot delete the last admin user")

        # Delete from auth.users (cascade will handle public.users via RLS)
        self.supabase.auth.admin.delete_user(user_id)

        return True

    def reset_password(self, user_id: str) -> str:
        """
        Reset a user's password to a new generated password.

        Args:
            user_id: ID of user whose password to reset

        Returns:
            The new plain-text password

        Raises:
            ValueError: If user not found
        """
        existing = self.get_user(user_id)
        if not existing:
            raise ValueError("User not found")

        password = generate_secure_password()

        self.supabase.auth.admin.update_user_by_id(
            user_id,
            {"password": password}
        )

        return password


_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    """Lazy initialization — only create the client when first needed."""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
