"""
Per-user module permissions.

Educational Note: This module handles granular feature access control.
Each user has a `permissions` JSONB column on the users table. NULL means
"all enabled" (the default). When an admin customizes a user's access,
the full structure is stored.

Five categories, each with a master toggle (`enabled`) and individual
sub-item toggles (`items`):

1. document_sources — PDF, DOCX, PPTX, Image, Audio, URL/YouTube, Text, Google Drive
2. data_sources     — Database, CSV, Freshdesk (the sensitive data access)
3. studio           — All 18 content generation types
4. integrations     — Jira, Notion, MCP, ElevenLabs
5. chat_features    — Memory, Voice Input, Chat Export
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _get_default_permissions() -> Dict[str, Any]:
    """
    Return the all-enabled permission structure.

    Educational Note: This is the baseline — every feature on. Admins
    selectively disable features per user. The structure is stored as
    JSONB on users.permissions when customized.
    """
    return {
        "document_sources": {
            "enabled": True,
            "items": {
                "pdf": True,
                "docx": True,
                "pptx": True,
                "image": True,
                "audio": True,
                "url_youtube": True,
                "text": True,
                "google_drive": True,
            },
        },
        "data_sources": {
            "enabled": True,
            "items": {
                "database": True,
                "csv": True,
                "freshdesk": True,
            },
        },
        "studio": {
            "enabled": True,
            "items": {
                "audio_overview": True,
                "ad_creative": True,
                "flash_cards": True,
                "flow_diagrams": True,
                "infographics": True,
                "mind_maps": True,
                "quizzes": True,
                "social_posts": True,
                "emails": True,
                "websites": True,
                "components": True,
                "videos": True,
                "wireframes": True,
                "presentations": True,
                "prds": True,
                "marketing_strategies": True,
                "blogs": True,
                "business_reports": True,
            },
        },
        "integrations": {
            "enabled": True,
            "items": {
                "jira": True,
                "notion": True,
                "mcp": True,
                "elevenlabs": True,
            },
        },
        "chat_features": {
            "enabled": True,
            "items": {
                "memory": True,
                "voice_input": True,
                "chat_export": True,
            },
        },
    }


# Exported constant for API responses and frontend type generation
DEFAULT_PERMISSIONS = _get_default_permissions()


def _get_supabase():
    """Lazy import to avoid circular dependencies."""
    from app.services.integrations.supabase import get_supabase
    return get_supabase()


def get_user_permissions(user_id: str) -> Dict[str, Any]:
    """
    Load permissions for a user. Returns the stored JSONB if customized,
    or the all-enabled default if NULL.

    Educational Note: NULL in the database means "use defaults" — this
    avoids writing 50+ boolean fields for every new user.
    """
    try:
        client = _get_supabase()
        response = (
            client.table("users")
            .select("permissions")
            .eq("id", user_id)
            .execute()
        )
        if not response.data:
            return _get_default_permissions()

        stored = response.data[0].get("permissions")
        if stored is None:
            return _get_default_permissions()

        # Merge with defaults to pick up any new categories/items added
        # after the user's permissions were last saved.
        defaults = _get_default_permissions()
        return _merge_with_defaults(stored, defaults)
    except Exception as e:
        logger.error("Failed to load permissions for user %s: %s", user_id, e)
        return _get_default_permissions()


def _merge_with_defaults(stored: Dict, defaults: Dict) -> Dict:
    """
    Merge stored permissions with defaults so new categories/items
    added in code are automatically enabled for existing users.
    """
    merged = {}
    for category, default_cat in defaults.items():
        if category not in stored:
            merged[category] = default_cat
            continue

        stored_cat = stored[category]
        merged[category] = {
            "enabled": stored_cat.get("enabled", default_cat["enabled"]),
            "items": {},
        }

        for item, default_val in default_cat["items"].items():
            stored_items = stored_cat.get("items", {})
            merged[category]["items"][item] = stored_items.get(item, default_val)

    return merged


def update_user_permissions(user_id: str, permissions: Dict[str, Any]) -> bool:
    """
    Save customized permissions to the users table.

    Args:
        user_id: The user UUID
        permissions: Full permissions structure

    Returns:
        True if saved successfully
    """
    try:
        client = _get_supabase()
        response = (
            client.table("users")
            .update({"permissions": permissions})
            .eq("id", user_id)
            .execute()
        )
        return bool(response.data)
    except Exception as e:
        logger.error("Failed to update permissions for user %s: %s", user_id, e)
        return False


def user_has_permission(user_id: str, category: str, item: Optional[str] = None) -> bool:
    """
    Check if a user has access to a specific feature.

    Educational Note: Three-level check:
    1. If permissions is NULL → all enabled (default)
    2. If category.enabled is False → entire category disabled
    3. If item specified and items[item] is False → specific item disabled

    Args:
        user_id: The user UUID
        category: One of the 5 category keys (e.g., "data_sources")
        item: Optional sub-item key (e.g., "database")

    Returns:
        True if the user has access
    """
    perms = get_user_permissions(user_id)

    cat = perms.get(category)
    if cat is None:
        return True  # Unknown category = allowed

    if not cat.get("enabled", True):
        return False  # Entire category disabled

    if item is None:
        return True  # Category-level check passed

    return cat.get("items", {}).get(item, True)
