"""
Text Upload Handler - Manages pasted text source uploads to Supabase Storage.

Educational Note: Pasted text is uploaded to Supabase Storage as a .txt file.
This is the simplest source type - the raw content IS the processed content
(after adding page markers for large texts).
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any

from app.services.source_services import source_index_service
from app.services.background_services import task_service
from app.services.integrations.supabase import storage_service

logger = logging.getLogger(__name__)


def upload_text(
    project_id: str,
    content: str,
    name: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Add a pasted text source to a project (uploads to Supabase Storage).

    Educational Note: Pasted text is uploaded to Supabase Storage as a .txt file.
    Processing will add page markers for large texts.

    Args:
        project_id: The project UUID
        content: The pasted text content
        name: Display name for the source (required)
        description: Optional description

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If content or name is empty
    """
    # Validate inputs
    if not content or not content.strip():
        raise ValueError("Content cannot be empty")

    if not name or not name.strip():
        raise ValueError("Name is required for pasted text")

    content = content.strip()
    name = name.strip()

    # Generate source ID and filename
    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.txt"

    # Convert content to bytes for upload
    file_data = content.encode('utf-8')
    file_size = len(file_data)

    # Upload to Supabase Storage
    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=file_data,
        content_type="text/plain"
    )

    if not storage_path:
        raise ValueError("Failed to upload text to storage")

    # Create source metadata (matching file_upload.py format)
    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": name,
        "description": description,
        "type": "TEXT",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": file_size,
        "is_active": False,
        "embedding_info": {
            "original_filename": f"{name}.txt",
            "mime_type": "text/plain",
            "file_extension": ".txt",
            "stored_filename": stored_filename,
            "source_type": "pasted_text"
        }
    }

    # Add to Supabase sources table
    source_index_service.add_source_to_index(project_id, source_metadata)

    # Submit processing as background task
    _submit_processing_task(project_id, source_id)

    return source_metadata


def update_text(
    project_id: str,
    source_id: str,
    content: str,
    name: str = None,
) -> Dict[str, Any]:
    """
    Replace a TEXT source's body content and re-run the processing
    pipeline so chunks + embeddings reflect the edit.

    Educational Note: TEXT sources are the only type the in-app editor
    can produce, so they're the only type we know how to round-trip
    through the editor → backend → processed-text path. Other types
    (PDF, DOCX, ...) require re-upload, which the existing delete +
    re-create flow already handles.

    Pipeline:
      1. Verify the source exists and is type=TEXT
      2. Overwrite raw file (Supabase Storage upload is upsert)
      3. Delete the previous processed file + chunks so the chunker
         doesn't need to merge old vs new pages
      4. Reset status to "uploaded" + update name/file_size
      5. Submit a new processing task — the same one initial upload
         uses, so chunks + Pinecone embeddings rebuild from scratch

    Args:
        project_id: project UUID
        source_id: source UUID — must exist and be TEXT
        content: new body (markdown / plain text)
        name: optional rename; if None, the existing name is kept

    Returns:
        Updated source metadata dict.

    Raises:
        ValueError: empty content, name blank-after-strip, or wrong type.
    """
    from app.services.source_services import source_service
    from app.services.integrations.supabase import storage_service as storage

    if not content or not content.strip():
        raise ValueError("Content cannot be empty")

    source = source_service.get_source(project_id, source_id)
    if not source:
        raise ValueError("Source not found")

    if (source.get("type") or "").upper() != "TEXT":
        # Editing other source types means re-uploading the binary —
        # not what this endpoint promises. Frontend gates the Edit
        # button to TEXT, but defend in depth.
        raise ValueError(
            f"Only TEXT sources can be edited in-place "
            f"(this source is {source.get('type')})"
        )

    embedding_info = source.get("embedding_info") or {}
    stored_filename = embedding_info.get("stored_filename") or f"{source_id}.txt"

    content = content.strip()
    file_data = content.encode("utf-8")
    file_size = len(file_data)

    # Snapshot the *previous* body before overwriting. This gives us
    # "view earlier versions" history. Failure to snapshot is a soft
    # error — never block the save on it.
    try:
        prev_bytes = storage.download_raw_file(project_id, source_id, stored_filename)
        if prev_bytes:
            prev_text = prev_bytes.decode("utf-8", errors="replace")
            from app.services.source_services import source_version_service
            source_version_service.record_version(
                source_id=source_id,
                content=prev_text,
                name=source.get("name") or "Untitled",
            )
    except Exception as e:
        logger.warning("Pre-edit snapshot failed for %s: %s", source_id, e)

    # 1. Overwrite raw file. upload_raw_file is upsert — same path,
    #    new bytes.
    storage_path = storage.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=file_data,
        content_type="text/plain",
    )
    if not storage_path:
        raise ValueError("Failed to upload edited content")

    # 2. Clear previously-derived data. The processor will rebuild
    #    these from scratch — partial leftovers would survive into the
    #    next chunking pass.
    storage.delete_processed_file(project_id, source_id)
    storage.delete_source_chunks(project_id, source_id)

    # 3. Update metadata. Status drops to uploaded so the chunker /
    #    embedder treat this as a fresh job.
    update_kwargs = {
        "status": "uploaded",
        "file_size": file_size,
    }
    if name and name.strip():
        update_kwargs["name"] = name.strip()
    source_service.update_source(project_id, source_id, **update_kwargs)

    # 4. Kick off background processing using the same task path as
    #    the initial upload. The status flip to "processing" lives
    #    inside _submit_processing_task.
    _submit_processing_task(project_id, source_id)

    # Return the freshest read so the caller can render the new state
    # without an extra round trip.
    return source_service.get_source(project_id, source_id)


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """
    Submit a background task to process the text source.

    Educational Note: Even text files go through processing to add
    page markers for consistent chunking behavior.
    """
    try:
        from app.services.source_services.source_processing import source_processing_service
        from app.services.source_services import source_service

        task_id = task_service.submit_task(
            "source_processing",
            source_id,
            source_processing_service.process_source,
            project_id,
            source_id
        )

        # Update status to "processing" immediately
        source_service.update_source(project_id, source_id, status="processing")
    except Exception as e:
        logger.error("Failed to submit text processing task for source %s: %s", source_id, e)
