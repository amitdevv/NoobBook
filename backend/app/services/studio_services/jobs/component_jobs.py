"""
UI Component Job Management - Tracks component generation jobs.

Educational Note: Component jobs use AI to generate reusable UI components
(buttons, cards, forms, etc.) with multiple variations using HTML/CSS/Tailwind.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "component"


def create_component_job(
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
        "component_category": None,
        "component_description": None,
        "variations_planned": [],
        "technical_notes": None,
        "components": [],
        "usage_notes": None,
        "iterations": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_component_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_component_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_component_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_component_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
