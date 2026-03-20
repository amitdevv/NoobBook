"""
Freshdesk Upload Handler - Create a FRESHDESK source from configured Freshdesk account.

Educational Note: A Freshdesk source is represented similarly to database sources:
- We store a small `.freshdesk` "raw file" in Supabase Storage that contains
  non-secret metadata (domain, created_at).
- The actual API key lives in the environment variable FRESHDESK_API_KEY.
- Processing syncs tickets and generates a processed text summary for the source.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.background_services import task_service
from app.services.integrations.freshdesk.freshdesk_service import freshdesk_service
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service

logger = logging.getLogger(__name__)


def add_freshdesk_source(
    project_id: str,
    name: Optional[str] = None,
    description: str = "",
    days_back: int = 30,
) -> Dict[str, Any]:
    """
    Create a FRESHDESK source in a project and trigger processing.

    Args:
        project_id: The project UUID
        name: Optional display name in the Sources list
        description: Optional description
        days_back: Number of days of ticket history to backfill

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If Freshdesk is not configured
    """
    if not freshdesk_service.is_configured():
        raise ValueError(
            "Freshdesk not configured. Please add FRESHDESK_API_KEY and "
            "FRESHDESK_DOMAIN to your .env file."
        )

    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.freshdesk"

    raw_payload = {
        "kind": "freshdesk_source",
        "days_back": days_back,
        "created_at": datetime.now().isoformat(),
    }

    # Upload raw metadata "file" (no credentials)
    raw_bytes = json.dumps(raw_payload, indent=2).encode("utf-8")
    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=raw_bytes,
        content_type="application/json; charset=utf-8",
    )
    if not storage_path:
        raise ValueError("Failed to create Freshdesk source metadata in storage")

    # Create source metadata
    display_name = (name or "Freshdesk Tickets").strip()
    if not display_name:
        display_name = "Freshdesk Tickets"

    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": display_name,
        "description": description,
        "type": "FRESHDESK",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": len(raw_bytes),
        "is_active": False,
        "embedding_info": {
            "original_filename": stored_filename,
            "mime_type": "application/json",
            "file_extension": ".freshdesk",
            "stored_filename": stored_filename,
            "source_type": "freshdesk",
            "days_back": days_back,
        },
        "processing_info": {
            "created_at": datetime.now().isoformat(),
            "note": "Freshdesk source created. Processing will sync tickets.",
        },
    }

    source_index_service.add_source_to_index(project_id, source_metadata)

    # Trigger processing in background
    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """Submit a background task to process the Freshdesk source."""
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

        # Update status immediately
        source_service.update_source(project_id, source_id, status="processing")
    except Exception as e:
        logger.error(
            "Failed to submit Freshdesk processing task for source %s: %s",
            source_id,
            e,
        )
