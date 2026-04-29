"""
Source version history — append-only snapshots of TEXT source bodies.

Each in-place edit (text_upload.update_text) records a row here BEFORE
the new content overwrites the raw file. The editor offers users a
"view / restore" affordance built on these snapshots.

Schema (see migration 00026_source_versions.sql):
    id          UUID PK
    source_id   UUID FK sources(id) ON DELETE CASCADE
    content     TEXT — full markdown body at snapshot time
    name        TEXT — display name at snapshot time
    created_at  TIMESTAMPTZ
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.integrations.supabase import get_supabase

logger = logging.getLogger(__name__)


def record_version(
    source_id: str,
    content: str,
    name: str,
) -> Optional[Dict[str, Any]]:
    """
    Insert a snapshot row. Returns the inserted row or None on error.

    The caller invokes this RIGHT BEFORE overwriting the raw file so
    "previous version" semantics line up with the user's mental model.
    """
    if not content or not content.strip():
        return None
    try:
        client = get_supabase()
        result = client.table("source_versions").insert({
            "source_id": source_id,
            "content": content,
            "name": name,
        }).execute()
        rows = getattr(result, "data", None) or []
        return rows[0] if rows else None
    except Exception as e:
        # Versioning is a nice-to-have; never let it break the save.
        logger.warning("Failed to record source version for %s: %s", source_id, e)
        return None


def list_versions(source_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    List versions for a source, newest first. Excludes the `content`
    field to keep the list response small — fetch full content via
    get_version when the user picks one.
    """
    try:
        client = get_supabase()
        result = (
            client.table("source_versions")
            .select("id, source_id, name, created_at")
            .eq("source_id", source_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return getattr(result, "data", None) or []
    except Exception as e:
        logger.error("Failed to list versions for %s: %s", source_id, e)
        return []


def get_version(version_id: str) -> Optional[Dict[str, Any]]:
    """Get a full version row including its `content`."""
    try:
        client = get_supabase()
        result = (
            client.table("source_versions")
            .select("*")
            .eq("id", version_id)
            .single()
            .execute()
        )
        return getattr(result, "data", None)
    except Exception as e:
        logger.error("Failed to fetch version %s: %s", version_id, e)
        return None
