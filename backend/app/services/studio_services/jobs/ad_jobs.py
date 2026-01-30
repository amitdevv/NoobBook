"""
Ad Creative Job Management - Tracks ad image generation jobs.

Educational Note: Ad jobs generate marketing creatives using AI image generation.
Creates multiple ad variations for products based on source content.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "ad"


def create_ad_job(
    project_id: str,
    job_id: str,
    product_name: str,
    direction: str
) -> Dict[str, Any]:
    job_data = {
        "id": job_id,
        "direction": direction,
        "status": "pending",
        "progress": "Initializing...",
        "error": None,
        "product_name": product_name,
        "images": [],
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_ad_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_ad_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_ad_jobs(project_id: str) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE)
