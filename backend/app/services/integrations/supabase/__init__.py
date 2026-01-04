"""
Supabase integration module.

This module provides services for interacting with Supabase:
- supabase_client: Centralized client initialization
- auth_service: User authentication and session management
"""

from .supabase_client import get_supabase, is_supabase_enabled, SupabaseClient
from .auth_service import auth_service, AuthService

__all__ = [
    "get_supabase",
    "is_supabase_enabled",
    "SupabaseClient",
    "auth_service",
    "AuthService",
]
