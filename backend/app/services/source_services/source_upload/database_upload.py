"""
Database Upload Handler - Create a DATABASE source from an account-level DB connection.

Educational Note: A database source is represented similarly to URL sources:
- We store a small `.database` "raw file" in Supabase Storage that contains
  non-secret metadata (connection_id, db_type, database_name).
- The actual credentials live in the account-level database_connections table.
- Processing fetches schema + generates a processed text snapshot for RAG + summaries.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.services.background_services import task_service
from app.services.data_services.database_connection_service import (
    database_connection_service,
    DEFAULT_USER_ID,
)
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service


def add_database_source(
    project_id: str,
    connection_id: str,
    name: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    """
    Create a DATABASE source in a project and trigger processing.

    Args:
        project_id: The project UUID
        connection_id: UUID of the database connection (account-level)
        name: Optional display name in the Sources list
        description: Optional description

    Returns:
        Source metadata dictionary
    """
    if not connection_id:
        raise ValueError("connection_id is required")

    # Load connection (server-side secret)
    connection = database_connection_service.get_connection(
        connection_id=connection_id,
        user_id=DEFAULT_USER_ID,
        include_secret=True,
    )
    if not connection:
        raise ValueError("Database connection not found (or not accessible)")

    db_type = connection.get("db_type")
    connection_uri = connection.get("connection_uri") or ""

    parsed = urlparse(connection_uri)
    database_name = (parsed.path or "").lstrip("/") or ""

    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.database"

    raw_payload = {
        "kind": "database_source",
        "connection_id": connection_id,
        "db_type": db_type,
        "database_name": database_name,
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
        raise ValueError("Failed to create database source metadata in storage")

    # Create source metadata
    display_name = (name or connection.get("name") or "Database").strip()
    if not display_name:
        display_name = "Database"

    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": display_name,
        "description": description,
        "type": "DATABASE",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": len(raw_bytes),
        "is_active": False,
        "embedding_info": {
            "original_filename": stored_filename,
            "mime_type": "application/json",
            "file_extension": ".database",
            "stored_filename": stored_filename,
            "source_type": "database",
            # Database metadata (no secrets)
            "connection_id": connection_id,
            "db_type": db_type,
            "database_name": database_name,
        },
        "processing_info": {
            "created_at": datetime.now().isoformat(),
            "note": "Database source created. Processing will fetch schema snapshot.",
        },
    }

    source_index_service.add_source_to_index(project_id, source_metadata)
    print(f"Created database source: {display_name} ({source_id})")

    # Trigger processing in background (uses existing source_processing_service)
    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """Submit a background task to process the database source."""
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

        # Update status immediately
        source_service.update_source(project_id, source_id, status="processing")
    except Exception as e:
        print(f"ERROR: Failed to submit database processing task: {e}")

