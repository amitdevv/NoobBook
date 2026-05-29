"""Shared base for Supabase-backed data services."""
from app.services.integrations.supabase import get_supabase, is_supabase_enabled


class SupabaseService:
    """Base for data services that talk to Supabase.

    Centralizes the configuration guard every CRUD service repeated verbatim:
    fail fast with a clear message if Supabase isn't set up, then expose the
    shared client as ``self.supabase``. Subclasses call ``super().__init__()``
    and then set their own table names.
    """

    def __init__(self) -> None:
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        self.supabase = get_supabase()
