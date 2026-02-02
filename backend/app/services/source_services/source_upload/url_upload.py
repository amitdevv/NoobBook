"""
URL Upload Handler - Manages URL source uploads to Supabase Storage.

Educational Note: URLs are stored as .link files containing JSON with the URL
and metadata. The actual content fetching/processing happens in a separate step
via the web_agent_service (for websites) or youtube_service (for YouTube).

Supports:
- Website URLs (processed by web_agent)
- YouTube URLs (processed by youtube_service)
"""
import json
import re
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from app.services.source_services import source_index_service
from app.services.background_services import task_service
from app.services.integrations.supabase import storage_service


def upload_url(
    project_id: str,
    url: str,
    name: Optional[str] = None,
    description: str = ""
) -> Dict[str, Any]:
    """
    Add a URL source (website or YouTube link) to a project.

    Educational Note: URLs are uploaded to Supabase Storage as .link files
    containing JSON with the URL and metadata. The actual content fetching
    happens in a separate processing step.

    Args:
        project_id: The project UUID
        url: The URL to store
        name: Optional display name (defaults to URL)
        description: Optional description

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If URL is empty or invalid format
    """
    # Basic URL validation
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")

    url = url.strip()

    # Auto-prepend https:// if no protocol specified (safety net for frontend)
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = f"https://{url}"

    # Check if it looks like a URL
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        raise ValueError("Invalid URL format. Must start with http:// or https://")

    # Detect if it's a YouTube URL
    is_youtube = 'youtube.com' in url.lower() or 'youtu.be' in url.lower()
    link_type = 'youtube' if is_youtube else 'website'

    # Generate source ID and filename
    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.link"

    # Create link file with URL data
    link_data = {
        "url": url,
        "type": link_type,
        "fetched": False,
        "fetched_at": None
    }

    # Convert to bytes for upload
    file_data = json.dumps(link_data, indent=2).encode('utf-8')
    file_size = len(file_data)

    # Upload to Supabase Storage
    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=file_data,
        content_type="application/json"
    )

    if not storage_path:
        raise ValueError("Failed to upload URL to storage")

    # Create source metadata (matching text_upload.py format)
    # Type is YOUTUBE for YouTube links, LINK for websites
    source_type = "YOUTUBE" if is_youtube else "LINK"
    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": name or url,
        "description": description,
        "type": source_type,
        "url": url,  # Store the URL directly in the url column
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": file_size,
        "is_active": False,
        "embedding_info": {
            "original_filename": url,
            "mime_type": "application/json",
            "file_extension": ".link",
            "stored_filename": stored_filename,
            "source_type": "url"
        },
        "processing_info": {"link_type": link_type}
    }

    # Add to Supabase sources table
    source_index_service.add_source_to_index(project_id, source_metadata)

    print(f"Uploaded URL source to Supabase: {url} ({source_id})")

    # Submit background processing task
    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """
    Submit a background task to process the URL source.

    Educational Note: URL content extraction runs in background thread
    so it doesn't block the API response.
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
        print(f"ERROR: Failed to submit URL processing task: {e}")
