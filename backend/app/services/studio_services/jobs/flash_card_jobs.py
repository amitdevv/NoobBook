"""
Flash Card Job Management - Tracks flash card generation jobs.

Educational Note: Flash card jobs use AI to extract key concepts from source
content and generate question-answer pairs for studying.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "flash_card"


def create_flash_card_job(
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
        "cards": [],
        "topic_summary": None,
        "card_count": 0,
        "generation_time_seconds": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_flash_card_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_flash_card_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_flash_card_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_flash_card_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
