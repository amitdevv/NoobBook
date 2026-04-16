"""
Jira Upload Handler - Create a JIRA source flag for a project.

Educational Note: Unlike Freshdesk sources that sync data locally, Jira sources
are lightweight "flags" that enable the existing Jira API tools (jira_list_projects,
jira_search_issues, jira_get_issue, jira_get_project) for a specific project.
No data is synced or stored locally — all queries go directly to the Jira API.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.background_services import task_service
from app.services.integrations.knowledge_bases.jira.jira_service import jira_service
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service

logger = logging.getLogger(__name__)


def add_jira_source(
    project_id: str,
    name: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    """
    Create a JIRA source in a project and trigger processing.

    Educational Note: This is a lightweight source that acts as a per-project
    flag to enable Jira tools in chat. The processing step verifies the Jira
    connection and builds a summary of available projects.

    Args:
        project_id: The project UUID
        name: Optional display name in the Sources list
        description: Optional description

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If Jira is not configured
    """
    if not jira_service.is_configured():
        raise ValueError(
            "Jira not configured. Please add JIRA_EMAIL, JIRA_API_KEY, and "
            "either JIRA_CLOUD_ID or JIRA_DOMAIN to your .env file."
        )

    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.jira"

    raw_payload = {
        "kind": "jira_source",
        "created_at": datetime.now().isoformat(),
    }

    # Upload raw metadata "file" (no credentials stored)
    raw_bytes = json.dumps(raw_payload, indent=2).encode("utf-8")
    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=raw_bytes,
        content_type="application/json; charset=utf-8",
    )
    if not storage_path:
        raise ValueError("Failed to create Jira source metadata in storage")

    # Create source metadata
    display_name = (name or "Jira Projects").strip()
    if not display_name:
        display_name = "Jira Projects"

    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": display_name,
        "description": description,
        "type": "JIRA",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": len(raw_bytes),
        "is_active": False,
        "embedding_info": {
            "original_filename": stored_filename,
            "mime_type": "application/json",
            "file_extension": ".jira",
            "stored_filename": stored_filename,
            "source_type": "jira",
            "is_global": False,
        },
        "processing_info": {
            "created_at": datetime.now().isoformat(),
            "note": "Jira source created. Processing will verify connection.",
        },
    }

    source_index_service.add_source_to_index(project_id, source_metadata)

    # Submit processing task to verify connection and build summary
    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """Submit a background task to process the Jira source."""
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
            "Failed to submit Jira processing task for source %s: %s",
            source_id,
            e,
        )
