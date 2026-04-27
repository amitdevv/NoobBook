"""
Share Service — CRUD over the project_shares table (Roadmap #15).

A share is a token that grants read-only access to a project's chats.
Two modes:

* **public**  — anyone with the URL gets access (no auth required).
* **invited** — only logged-in users whose email matches a row in
  ``invited_emails`` get access.

Shares can be **revoked** (sets ``revoked_at``) or **expire** (the
``expires_at`` timestamp passes). Either condition makes the share
inactive — the row stays in the table for audit but lookup fails.

Token generation uses ``secrets.token_urlsafe(32)`` (256 bits of entropy,
URL-safe base64), making brute-force enumeration infeasible. Tokens are
unique-indexed at the DB level.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)

# Token byte length — token_urlsafe(32) returns ~43 chars (32 bytes b64).
_TOKEN_BYTES = 32

VALID_MODES = {"public", "invited"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_active(row: Dict[str, Any]) -> bool:
    """Mirrors the SQL is_share_active() function for in-process checks."""
    if not row:
        return False
    if row.get("revoked_at"):
        return False
    expires_at = row.get("expires_at")
    if expires_at:
        # Supabase returns ISO strings; normalize for comparison.
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except Exception:
                return False
        if expires_at <= _now():
            return False
    return True


def _generate_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def _client():
    if not is_supabase_enabled():
        raise RuntimeError("Supabase is not configured.")
    return get_supabase()


def create_share(
    project_id: str,
    created_by: str,
    mode: str,
    invited_emails: Optional[List[str]] = None,
    expires_in_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a new share row for a project.

    Args:
        project_id: The project being shared.
        created_by: The owner user's id (already validated upstream).
        mode: "public" or "invited".
        invited_emails: Required and non-empty when mode == "invited".
                        Lower-cased and de-duped for stable matching.
        expires_in_days: 7, 30, or None. None means the share never expires.

    Returns:
        The inserted row (including the generated token).
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    normalized_emails: List[str] = []
    if mode == "invited":
        if not invited_emails:
            raise ValueError("invited mode requires at least one email")
        # Lower-case + de-dup. We compare against `users.email` which Supabase
        # also stores lower-cased, so consistent casing avoids subtle misses.
        seen = set()
        for raw in invited_emails:
            if not raw:
                continue
            email = raw.strip().lower()
            if email and email not in seen:
                seen.add(email)
                normalized_emails.append(email)
        if not normalized_emails:
            raise ValueError("invited mode requires at least one valid email")

    expires_at: Optional[str] = None
    if expires_in_days is not None:
        if expires_in_days <= 0:
            raise ValueError("expires_in_days must be positive (or None for never)")
        expires_at = (_now() + timedelta(days=expires_in_days)).isoformat()

    row = {
        "project_id": project_id,
        "token": _generate_token(),
        "mode": mode,
        "invited_emails": normalized_emails,
        "created_by": created_by,
        "expires_at": expires_at,
    }

    client = _client()
    response = client.table("project_shares").insert(row).execute()
    if not response.data:
        raise RuntimeError("Failed to create project share")
    return response.data[0]


def list_shares_for_project(project_id: str) -> List[Dict[str, Any]]:
    """List all share rows for a project (active + revoked + expired)."""
    client = _client()
    response = (
        client.table("project_shares")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def get_share_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Look up a share by its token. Returns the raw row regardless of
    active/revoked/expired status — callers decide what to do with it."""
    if not token:
        return None
    client = _client()
    response = (
        client.table("project_shares")
        .select("*")
        .eq("token", token)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def get_share_by_id(share_id: str, project_id: str) -> Optional[Dict[str, Any]]:
    """Look up a specific share row scoped to a project (for owner ops)."""
    client = _client()
    response = (
        client.table("project_shares")
        .select("*")
        .eq("id", share_id)
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def revoke_share(share_id: str, project_id: str) -> bool:
    """Mark a share as revoked. Idempotent — already-revoked shares
    return True without re-stamping the timestamp."""
    existing = get_share_by_id(share_id, project_id)
    if not existing:
        return False
    if existing.get("revoked_at"):
        return True
    client = _client()
    client.table("project_shares").update({
        "revoked_at": _now().isoformat(),
    }).eq("id", share_id).eq("project_id", project_id).execute()
    return True


def is_share_usable(row: Dict[str, Any]) -> bool:
    """Public wrapper around the active check so callers don't import _is_active."""
    return _is_active(row)


def email_invited(row: Dict[str, Any], email: Optional[str]) -> bool:
    """For invited mode: check that the viewer's email is in the allow-list.
    Public mode always returns True (mode-mismatch is the caller's job)."""
    if row.get("mode") == "public":
        return True
    if not email:
        return False
    invited = row.get("invited_emails") or []
    return email.strip().lower() in {e.lower() for e in invited if e}
