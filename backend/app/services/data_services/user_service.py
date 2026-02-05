"""
User Service - Admin-oriented user management (roles, create, delete).

Note: This service uses a dedicated Supabase client for admin operations.
The shared singleton client gets user sessions set on it during sign-in,
which causes auth.admin methods to use the user's token instead of the
service_role key. By creating a separate client here, we ensure admin
operations always use the service_role key.
"""
import os
from typing import Dict, List, Optional, Tuple

from supabase import create_client

from app.services.integrations.supabase import is_supabase_enabled
from app.utils.password_utils import generate_secure_password


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

        # Create profile in public.users
        self.supabase.table(self.table).insert({
            "id": user_id,
            "email": email,
            "role": role,
            "memory": {},
            "settings": {}
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


user_service = UserService()

