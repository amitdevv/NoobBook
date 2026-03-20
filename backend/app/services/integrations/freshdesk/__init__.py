"""
Freshdesk Integration Module - Freshdesk API client and sync services.

Educational Note: This module provides two services:
- freshdesk_service: API client for interacting with the Freshdesk REST API
- freshdesk_sync_service: Syncs ticket data into local Supabase tables for analysis
"""

from .freshdesk_service import freshdesk_service
from .freshdesk_sync_service import freshdesk_sync_service

__all__ = [
    "freshdesk_service",
    "freshdesk_sync_service",
]
