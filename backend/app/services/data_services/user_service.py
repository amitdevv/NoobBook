"""
User Service - Admin-oriented user management (roles).
"""
from typing import Dict, List, Optional

from app.services.integrations.supabase import get_supabase, is_supabase_enabled


class UserService:
    def __init__(self) -> None:
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        self.supabase = get_supabase()
        self.table = "users"

    def list_users(self) -> List[Dict[str, str]]:
        resp = (
            self.supabase.table(self.table)
            .select("id, email, role, created_at, updated_at")
            .order("created_at", desc=False)
            .execute()
        )
        return resp.data or []

    def get_user(self, user_id: str) -> Optional[Dict[str, str]]:
        resp = (
            self.supabase.table(self.table)
            .select("id, email, role, created_at, updated_at")
            .eq("id", user_id)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

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


user_service = UserService()

