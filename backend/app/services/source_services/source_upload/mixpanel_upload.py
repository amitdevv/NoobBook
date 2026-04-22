"""
Mixpanel Upload Handler - Create a MIXPANEL source flag for a project.

Educational Note: Same lightweight pattern as jira_upload — the source acts
as a per-project flag that enables Mixpanel chat tools. No data is synced
locally; all queries go live to the Mixpanel Query API.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.background_services import task_service
from app.services.integrations.knowledge_bases.mixpanel.mixpanel_service import mixpanel_service
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service

logger = logging.getLogger(__name__)


def add_mixpanel_source(
    project_id: str,
    name: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    """
    Create a MIXPANEL source in a project and trigger processing.

    Args:
        project_id: The project UUID
        name: Optional display name in the Sources list
        description: Optional description

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If Mixpanel is not configured
    """
    if not mixpanel_service.is_configured():
        raise ValueError(
            "Mixpanel not configured. Please add MIXPANEL_SERVICE_ACCOUNT_USERNAME, "
            "MIXPANEL_SERVICE_ACCOUNT_SECRET, and MIXPANEL_PROJECT_ID to your .env file."
        )

    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.mixpanel"

    raw_payload = {
        "kind": "mixpanel_source",
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
        raise ValueError("Failed to create Mixpanel source metadata in storage")

    display_name = (name or "Mixpanel Analytics").strip()
    if not display_name:
        display_name = "Mixpanel Analytics"

    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": display_name,
        "description": description,
        "type": "MIXPANEL",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": len(raw_bytes),
        "is_active": True,
        "embedding_info": {
            "original_filename": stored_filename,
            "mime_type": "application/json",
            "file_extension": ".mixpanel",
            "stored_filename": stored_filename,
            "source_type": "mixpanel",
            "is_global": False,
        },
        "processing_info": {
            "created_at": datetime.now().isoformat(),
            "note": "Mixpanel source created. Processing will verify connection.",
        },
    }

    source_index_service.add_source_to_index(project_id, source_metadata)
    _submit_processing_task(project_id, source_id)
    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """Submit a background task to process the Mixpanel source."""
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
            "Failed to submit Mixpanel processing task for source %s: %s",
            source_id,
            e,
        )
