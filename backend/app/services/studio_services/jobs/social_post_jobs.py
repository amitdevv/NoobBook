"""
Social Post Job Management - Tracks social media post generation jobs.

Educational Note: Social post jobs use AI to generate platform-specific
content (Twitter, LinkedIn, etc.) from source materials.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "social_post"


def create_social_post_job(
    project_id: str,
    job_id: str,
    topic: str,
    direction: str
) -> Dict[str, Any]:
    job_data = {
        "id": job_id,
        "direction": direction,
        "status": "pending",
        "progress": "Initializing...",
        "error": None,
        "topic": topic,
        "posts": [],
        "topic_summary": None,
        "post_count": 0,
        "generation_time_seconds": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_social_post_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_social_post_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_social_post_jobs(project_id: str) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE)


def delete_social_post_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
