"""
Presentation Job Management - Tracks presentation generation jobs.

Educational Note: Presentations are generated as HTML slides that are
screenshotted at 1920x1080 and exported to PPTX format using python-pptx.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "presentation"


def create_presentation_job(
    project_id: str,
    job_id: str,
    source_id: str,
    source_name: str,
    direction: str
) -> Dict[str, Any]:
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
        "presentation_title": None,
        "presentation_type": None,
        "target_audience": None,
        "planned_slides": [],
        "design_system": None,
        "style_notes": None,
        "files": [],
        "slide_files": [],
        "slides_created": 0,
        "slides_metadata": [],
        "total_slides": 0,
        "summary": None,
        "design_notes": None,
        "screenshots": [],
        "pptx_file": None,
        "pptx_filename": None,
        "export_status": None,
        "preview_url": None,
        "download_url": None,
        "iterations": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_presentation_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_presentation_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_presentation_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_presentation_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
