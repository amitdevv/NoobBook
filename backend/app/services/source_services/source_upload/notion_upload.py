"""
Notion Upload Handler - Create a NOTION source for a project.

Notion sources work like Google Drive imports — the user
picks a specific Notion page or database in the browse-and-pick UI, and we
create a per-project source that resolves to that ID. The .notion stub holds
the picked ID + object_type; the processor fetches live content during
processing and embeds the result for RAG.

Unlike Jira/Mixpanel (live-only API flags), Notion content IS embedded —
pages are slow-changing knowledge artifacts that benefit from chunked
semantic search, not live querying.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.background_services import task_service
from app.services.integrations.knowledge_bases.notion.notion_service import notion_service
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service

logger = logging.getLogger(__name__)


VALID_OBJECT_TYPES = ("page", "database")


def add_notion_source(
    project_id: str,
    notion_id: str,
    object_type: str,
    title: Optional[str] = None,
    notion_url: Optional[str] = None,
    last_edited_time: Optional[str] = None,
    name: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    """
    Create a NOTION source in a project and trigger processing.

    Args:
        project_id: The project UUID
        notion_id: The Notion page or database UUID
        object_type: "page" or "database"
        title: Title fetched from Notion during the picker step (used for naming)
        notion_url: notion.so URL of the resource (for the preview header)
        last_edited_time: ISO timestamp from Notion (used in preview header)
        name: Optional display-name override; falls back to `title`
        description: Optional user description

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If Notion is not configured or arguments are invalid
    """
    if not notion_service.is_configured():
        raise ValueError(
            "Notion not configured. Add NOTION_API_KEY in Settings → API Keys."
        )
    if not notion_id:
        raise ValueError("notion_id is required")
    if object_type not in VALID_OBJECT_TYPES:
        raise ValueError(
            f"object_type must be one of {VALID_OBJECT_TYPES}, got '{object_type}'"
        )

    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.notion"

    raw_payload = {
        "kind": "notion_source",
        "notion_id": notion_id,
        "object_type": object_type,
        "title": title or "",
        "notion_url": notion_url or "",
        "last_edited_time": last_edited_time or "",
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
        raise ValueError("Failed to create Notion source metadata in storage")

    display_name = (name or title or f"Notion {object_type}").strip()
    if not display_name:
        display_name = f"Notion {object_type}"

    source_metadata: Dict[str, Any] = {
        "id": source_id,
        "project_id": project_id,
        "name": display_name,
        "description": description,
        "type": "NOTION",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": len(raw_bytes),
        "is_active": True,
        "embedding_info": {
            "original_filename": stored_filename,
            "mime_type": "application/json",
            "file_extension": ".notion",
            "stored_filename": stored_filename,
            "source_type": "notion",
            "notion_id": notion_id,
            "object_type": object_type,
            "notion_url": notion_url or "",
            "last_edited_time": last_edited_time or "",
        },
        "processing_info": {
            "created_at": datetime.now().isoformat(),
            "note": f"Notion {object_type} source created. Processing will fetch content.",
        },
    }

    source_index_service.add_source_to_index(project_id, source_metadata)

    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """Submit a background task to fetch + embed the Notion content."""
    try:
        from app.services.source_services.source_processing import (
            source_processing_service,
        )
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
        logger.error(
            "Failed to submit Notion processing task for source %s: %s",
            source_id,
            e,
        )
