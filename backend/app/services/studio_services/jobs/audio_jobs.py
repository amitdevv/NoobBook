"""
Audio Job Management - Tracks audio generation jobs.

Educational Note: Audio jobs generate podcast-style content from source materials.
Uses ElevenLabs for text-to-speech synthesis.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "audio"


def create_audio_job(
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
        "audio_path": None,
        "audio_filename": None,
        "audio_url": None,
        "script_path": None,
        "audio_info": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_audio_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_audio_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_audio_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_audio_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
