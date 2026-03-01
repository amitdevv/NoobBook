"""
Research Upload Handler - Manages deep research source creation.

Educational Note: Deep research sources are created by an AI agent that:
1. Searches the web for information on a topic
2. Analyzes any provided reference links
3. Synthesizes findings into a comprehensive document

The research request is uploaded to Supabase Storage as a .research JSON file containing:
- topic: The main research topic
- description: Focus areas and specific questions to answer
- links: Optional list of reference URLs to include
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List

from app.services.source_services import source_index_service
from app.services.background_services import task_service
from app.services.integrations.supabase import storage_service

logger = logging.getLogger(__name__)


def upload_research(
    project_id: str,
    topic: str,
    description: str,
    links: List[str] = None
) -> Dict[str, Any]:
    """
    Create a deep research source for a project.

    Educational Note: This uploads a .research file to Supabase Storage containing
    the research parameters. The actual research is performed by a background task
    using an AI agent with web search capabilities.

    Args:
        project_id: The project UUID
        topic: The main research topic (required)
        description: Focus areas and questions to answer (required, min 50 chars)
        links: Optional list of reference URLs to analyze

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If topic or description is invalid
    """
    # Validate inputs
    if not topic or not topic.strip():
        raise ValueError("Topic is required")

    if not description or len(description.strip()) < 50:
        raise ValueError("Description must be at least 50 characters")

    topic = topic.strip()
    description = description.strip()
    links = links or []

    # Validate links are proper URLs
    validated_links = []
    for link in links:
        link = link.strip()
        if link:
            # Basic URL validation - must start with http(s)://
            if not link.startswith(('http://', 'https://')):
                link = f"https://{link}"
            validated_links.append(link)

    # Generate source ID and filename
    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.research"

    # Create research request JSON
    research_request = {
        "topic": topic,
        "description": description,
        "links": validated_links,
        "created_at": datetime.now().isoformat()
    }

    # Upload to Supabase Storage (same pattern as text_upload.py and url_upload.py)
    file_data = json.dumps(research_request, indent=2).encode('utf-8')
    file_size = len(file_data)

    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=file_data,
        content_type="application/json"
    )

    if not storage_path:
        raise ValueError("Failed to upload research request to storage")

    # Create a display name from the topic (truncate if too long)
    display_name = topic if len(topic) <= 50 else topic[:47] + "..."

    # Create source metadata (matching text_upload.py / url_upload.py format)
    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": display_name,
        "description": description[:200] if len(description) > 200 else description,
        "type": "RESEARCH",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": file_size,
        "is_active": False,
        "embedding_info": {
            "original_filename": f"{display_name}.research",
            "mime_type": "application/json",
            "file_extension": ".research",
            "stored_filename": stored_filename,
            "source_type": "deep_research"
        },
        "processing_info": {
            "source_type": "deep_research",
            "topic": topic,
            "link_count": len(validated_links)
        }
    }

    # Add to index
    source_index_service.add_source_to_index(project_id, source_metadata)

    # Submit processing as background task
    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """
    Submit a background task to process the research source.

    Educational Note: Research processing can take several minutes as the
    AI agent searches the web and synthesizes findings. This runs in background.
    """
    from app.services.source_services.source_processing import source_processing_service

    task_service.submit_task(
        "source_processing",
        source_id,
        source_processing_service.process_source,
        project_id,
        source_id
    )
