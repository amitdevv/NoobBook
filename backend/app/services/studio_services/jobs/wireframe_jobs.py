"""
Wireframe Job Management - Tracks wireframe generation jobs.

Educational Note: Wireframes use Excalidraw elements to create
hand-drawn style UI prototypes, perfect for early-stage design.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "wireframe"


def create_wireframe_job(
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
        "title": None,
        "description": None,
        "elements": [],
        "canvas_width": 1200,
        "canvas_height": 800,
        "element_count": 0,
        "generation_time_seconds": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_wireframe_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_wireframe_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_wireframe_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_wireframe_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
