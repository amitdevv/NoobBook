"""
MCP Upload Handler - Create an MCP source from an account-level MCP connection.

Educational Note: An MCP source is represented similarly to database sources:
- We store a small `.mcp` "raw file" in Supabase Storage containing metadata
  (connection_id, selected resource URIs, timestamp).
- The actual server credentials live in the account-level mcp_connections table.
- Processing fetches resource content, builds processed text, and embeds for RAG.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.background_services import task_service

logger = logging.getLogger(__name__)
from app.services.data_services.mcp_connection_service import (
    mcp_connection_service,
    DEFAULT_USER_ID,
)
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service


def add_mcp_source(
    project_id: str,
    connection_id: str,
    resource_uris: List[str],
    name: Optional[str] = None,
    description: str = "",
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    """
    Create an MCP source in a project and trigger processing.

    Args:
        project_id: The project UUID
        connection_id: UUID of the MCP connection (account-level)
        resource_uris: List of MCP resource URIs to snapshot
        name: Optional display name in the Sources list
        description: Optional description

    Returns:
        Source metadata dictionary
    """
    if not connection_id:
        raise ValueError("connection_id is required")
    if not resource_uris:
        raise ValueError("At least one resource_uri is required")

    # Load connection (server-side)
    connection = mcp_connection_service.get_connection(
        connection_id=connection_id,
        user_id=user_id,
        include_secret=False,  # Don't need secrets for metadata
    )
    if not connection:
        raise ValueError("MCP connection not found (or not accessible)")

    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.mcp"

    # Raw metadata file (no credentials)
    raw_payload = {
        "kind": "mcp_source",
        "connection_id": connection_id,
        "resource_uris": resource_uris,
        "created_at": datetime.now().isoformat(),
    }

    raw_bytes = json.dumps(raw_payload, indent=2).encode("utf-8")
    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=raw_bytes,
        content_type="application/json; charset=utf-8",
    )
    if not storage_path:
        raise ValueError("Failed to create MCP source metadata in storage")

    display_name = (name or connection.get("name") or "MCP Resources").strip()
    if not display_name:
        display_name = "MCP Resources"

    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": display_name,
        "description": description,
        "type": "MCP",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": len(raw_bytes),
        # Live-connection sources are usable immediately — no extraction/embedding
        # required. Default checked so users don't have to toggle the eye icon
        # after adding the source.
        "is_active": True,
        "embedding_info": {
            "original_filename": stored_filename,
            "mime_type": "application/json",
            "file_extension": ".mcp",
            "stored_filename": stored_filename,
            "source_type": "mcp",
            "connection_id": connection_id,
            "resource_count": len(resource_uris),
        },
        "processing_info": {
            "created_at": datetime.now().isoformat(),
            "note": "MCP source created. Processing will snapshot selected resources.",
        },
    }

    source_index_service.add_source_to_index(project_id, source_metadata)

    # Trigger processing in background
    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """Submit a background task to process the MCP source."""
    try:
        from app.services.source_services.source_processing import source_processing_service
        from app.services.source_services import source_service

        task_service.submit_task(
            "source_processing",
            source_id,
            source_processing_service.process_source,
            project_id,
            source_id,
        )

        source_service.update_source(project_id, source_id, status="processing")
    except Exception as e:
        logger.error("Failed to submit MCP processing task for source %s: %s", source_id, e)
        # Mark source as error so it doesn't stay stuck in "uploaded" forever
        try:
            source_service.update_source(
                project_id, source_id,
                status="error",
                processing_info={"error": f"Failed to start processing: {e}"},
            )
        except Exception:
            logger.error("Could not mark source %s as error after task submission failure", source_id)
