"""
Website Job Management - Tracks website generation jobs.

Educational Note: Website jobs use an AI agent with iterative refinement to
generate multi-page static websites with HTML, CSS, and JavaScript.
Unlike email templates (single file), websites have multiple files created iteratively.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "website"


def create_website_job(
    project_id: str,
    job_id: str,
    source_id: str,
    source_name: str,
    direction: str
) -> None:
    """
    Create a new website generation job in Supabase.

    Educational Note: Tracks website generation with multi-file support.
    Unlike email templates (single HTML file), websites have multiple files
    (HTML pages, CSS, JS) that are created iteratively.
    """
    job_data = {
        "id": job_id,
        "source_id": source_id,
        "source_name": source_name,
        "direction": direction,
        "status": "pending",
        "progress": "Initializing...",
        "error": None,
        "status_message": "Initializing...",
        "error_message": None,
        "site_type": None,
        "site_name": None,
        "pages": [],
        "features": [],
        "design_system": None,
        "navigation_style": None,
        "images_needed": [],
        "layout_notes": None,
        "images": [],
        "files": [],
        "pages_created": [],
        "features_implemented": [],
        "cdn_libraries_used": [],
        "summary": None,
        "preview_url": None,
        "download_url": None,
        "iterations": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    create_job(project_id, JOB_TYPE, job_data)


def update_website_job(
    project_id: str,
    job_id: str,
    **updates
) -> None:
    """
    Update a website job with new information.

    Educational Note: Flexible updates for any job fields during
    the agent's iterative workflow. Unlike other job modules, this
    accepts ALL provided fields (including those with None/falsy values)
    to match the original behavior.
    """
    # Website jobs originally used `if key in job` not `if value is not None`,
    # so we pass all updates through. The generic update_job filters by
    # `if v is not None`, so we need to handle None values specially.
    update_job(project_id, job_id, **updates)


def get_website_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific website job by ID."""
    return get_job(project_id, job_id)


def list_website_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List website jobs, optionally filtered by source_id.

    Returns jobs sorted by created_at descending (newest first).
    """
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_website_job(project_id: str, job_id: str) -> bool:
    """
    Delete a website job.

    Returns:
        True if job was found and deleted
    """
    return delete_job(project_id, job_id)
