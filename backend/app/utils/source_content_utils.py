"""
Source Content Utilities - Shared functions for loading source content.

Used by multiple agents (blog, website, etc.) to get source content
with smart sampling for large sources.

Educational Note: Content is loaded from Supabase Storage (processed files
and chunks), not from local disk. All writes already go to Supabase;
this module switches the read path to match.
"""
from typing import Optional

from app.services.integrations.supabase import storage_service


def get_source_content(
    project_id: str,
    source_id: str,
    max_chars: int = 15000,
    max_chunks: int = 12
) -> str:
    """
    Get source content for AI processing.

    For small sources: returns full content.
    For large sources: samples chunks evenly distributed.

    Args:
        project_id: Project ID
        source_id: Source ID
        max_chars: Max characters before sampling (default 15000 ~3500 tokens)
        max_chunks: Max chunks to sample for large sources

    Returns:
        Source content string
    """
    try:
        from app.services.source_services import source_service

        source = source_service.get_source(project_id, source_id)
        if not source:
            return "Error: Source not found"

        # Download processed content from Supabase Storage
        full_content = storage_service.download_processed_file(project_id, source_id)

        if not full_content:
            return f"Source: {source.get('name', 'Unknown')}\n(Content not yet processed)"

        # Small source: return all
        if len(full_content) < max_chars:
            return full_content

        # Large source: try to sample chunks from Supabase Storage
        all_chunks = storage_service.list_source_chunks(project_id, source_id)

        if not all_chunks:
            return full_content[:max_chars] + "\n\n[Content truncated...]"

        # Sample chunks evenly distributed
        if len(all_chunks) <= max_chunks:
            selected_chunks = all_chunks
        else:
            step = len(all_chunks) / max_chunks
            selected_chunks = [all_chunks[int(i * step)] for i in range(max_chunks)]

        sampled_content = [chunk["text"] for chunk in selected_chunks]

        return "\n\n".join(sampled_content)

    except Exception as e:
        return f"Error loading source content: {str(e)}"


def get_source_name(project_id: str, source_id: str) -> Optional[str]:
    """Get source name by ID."""
    try:
        from app.services.source_services import source_service
        source = source_service.get_source(project_id, source_id)
        return source.get("name") if source else None
    except Exception:
        return None
