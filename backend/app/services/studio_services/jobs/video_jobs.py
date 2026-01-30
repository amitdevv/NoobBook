"""
Video Job Management - Tracks video generation jobs.

Educational Note: Video jobs use AI video generation APIs (like Google Veo)
to create short video clips from prompts derived from source content.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "video"


def create_video_job(
    project_id: str,
    job_id: str,
    source_id: str,
    source_name: str,
    direction: str,
    aspect_ratio: str = "16:9",
    duration_seconds: int = 8,
    number_of_videos: int = 1
) -> Dict[str, Any]:
    job_data = {
        "id": job_id,
        "source_id": source_id,
        "source_name": source_name,
        "direction": direction,
        "status": "pending",
        "progress": "Initializing...",
        "error": None,
        "aspect_ratio": aspect_ratio,
        "duration_seconds": duration_seconds,
        "number_of_videos": number_of_videos,
        "videos": [],
        "generated_prompt": None,
        "status_message": "Initializing...",
        "error_message": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_video_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_video_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_video_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_video_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
