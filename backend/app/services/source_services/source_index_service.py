"""
Source Index Service - CRUD operations for sources using Supabase.

Educational Note: This service manages source metadata in the Supabase `sources` table.
Sources represent uploaded files (PDFs, images, audio, URLs, text) that users add to projects.

Source status flow: uploaded → processing → [embedding] → ready
- uploaded: File received, not yet processed
- processing: AI extraction in progress
- embedding: Creating vector embeddings (for large sources)
- ready: Fully processed and searchable
- error: Processing failed
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.integrations.supabase import get_supabase, is_supabase_enabled


# Initialize Supabase client
def _get_client():
    """Get Supabase client, raising error if not configured."""
    if not is_supabase_enabled():
        raise RuntimeError(
            "Supabase is not configured. Please add SUPABASE_URL and "
            "SUPABASE_ANON_KEY to your .env file."
        )
    return get_supabase()


def load_index(project_id: str) -> Dict[str, Any]:
    """
    Load the sources index for a project.

    Educational Note: Returns structure compatible with old JSON format
    for backwards compatibility with existing code.

    Args:
        project_id: The project UUID

    Returns:
        Dict with "sources" list and "last_updated" timestamp
    """
    client = _get_client()

    response = (
        client.table("sources")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )

    # Map field names for frontend compatibility
    sources = [_map_source_fields(source) for source in (response.data or [])]

    return {
        "sources": sources,
        "last_updated": datetime.now().isoformat()
    }


def save_index(project_id: str, index_data: Dict[str, Any]) -> None:
    """
    Save the sources index for a project.

    Educational Note: This is a no-op for Supabase - data is saved
    immediately on insert/update. Kept for API compatibility.

    Args:
        project_id: The project UUID
        index_data: The index data (ignored)
    """
    # No-op for Supabase - data is saved immediately
    pass


def add_source_to_index(project_id: str, source_metadata: Dict[str, Any]) -> None:
    """
    Add a new source to the index.

    Args:
        project_id: The project UUID
        source_metadata: Complete source metadata dict
    """
    client = _get_client()

    # Map metadata to Supabase columns
    source_data = {
        "id": source_metadata.get("id"),
        "project_id": project_id,
        "name": source_metadata.get("name"),
        "description": source_metadata.get("description"),
        "type": source_metadata.get("type"),
        "status": source_metadata.get("status", "uploaded"),
        "raw_file_path": source_metadata.get("raw_file_path"),
        "processed_file_path": source_metadata.get("processed_file_path"),
        "token_count": source_metadata.get("token_count"),
        "page_count": source_metadata.get("page_count"),
        "file_size": source_metadata.get("file_size"),
        "embedding_info": source_metadata.get("embedding_info", {}),
        "summary_info": source_metadata.get("summary_info", {}),
        "processing_info": source_metadata.get("processing_info", {}),
        "error_message": source_metadata.get("error_message"),
        "url": source_metadata.get("url"),
        "is_active": source_metadata.get("is_active", True),
    }

    # Remove None values to use DB defaults
    source_data = {k: v for k, v in source_data.items() if v is not None}

    client.table("sources").insert(source_data).execute()

    print(f"  Added source to index: {source_metadata.get('name')} (ID: {source_metadata.get('id')})")


def remove_source_from_index(project_id: str, source_id: str) -> bool:
    """
    Remove a source from the index.

    Args:
        project_id: The project UUID
        source_id: The source UUID to remove

    Returns:
        True if source was found and removed, False otherwise
    """
    client = _get_client()

    # Check if exists first
    existing = (
        client.table("sources")
        .select("id")
        .eq("id", source_id)
        .eq("project_id", project_id)
        .execute()
    )

    if not existing.data:
        return False

    # Delete the source
    client.table("sources").delete().eq("id", source_id).eq("project_id", project_id).execute()

    print(f"  Removed source from index: {source_id}")
    return True


def _map_source_fields(source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Supabase column names to frontend field names.

    Educational Note: The Supabase table uses `is_active` but the frontend
    expects `active`. This function provides a consistent mapping.
    """
    if source is None:
        return None

    # Map is_active -> active for frontend compatibility
    if "is_active" in source:
        source["active"] = source.pop("is_active")

    return source


def get_source_from_index(project_id: str, source_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a source's metadata from the index.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        Source metadata dict or None if not found
    """
    client = _get_client()

    response = (
        client.table("sources")
        .select("*")
        .eq("id", source_id)
        .eq("project_id", project_id)
        .execute()
    )

    if response.data:
        return _map_source_fields(response.data[0])

    return None


def update_source_in_index(
    project_id: str,
    source_id: str,
    updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Update a source's metadata in the index.

    Educational Note: This is a generic update function. Pass a dict
    with the fields you want to update.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        updates: Dict of fields to update

    Returns:
        Updated source metadata or None if not found
    """
    client = _get_client()

    # Check if exists first
    existing = (
        client.table("sources")
        .select("id")
        .eq("id", source_id)
        .eq("project_id", project_id)
        .execute()
    )

    if not existing.data:
        return None

    # Filter to valid columns and remove None values
    valid_columns = {
        "name", "description", "type", "status", "raw_file_path",
        "processed_file_path", "token_count", "page_count", "file_size",
        "embedding_info", "summary_info", "processing_info", "error_message", "url", "is_active"
    }

    update_data = {k: v for k, v in updates.items() if k in valid_columns and v is not None}

    if not update_data:
        # Return existing data if no updates
        return get_source_from_index(project_id, source_id)

    # Update the source
    response = (
        client.table("sources")
        .update(update_data)
        .eq("id", source_id)
        .eq("project_id", project_id)
        .execute()
    )

    if response.data:
        return _map_source_fields(response.data[0])

    return get_source_from_index(project_id, source_id)


def list_sources_from_index(project_id: str) -> List[Dict[str, Any]]:
    """
    List all sources from the index, sorted by created_at (newest first).

    Args:
        project_id: The project UUID

    Returns:
        List of source metadata dicts
    """
    client = _get_client()

    response = (
        client.table("sources")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )

    # Map field names for frontend compatibility
    return [_map_source_fields(source) for source in (response.data or [])]
