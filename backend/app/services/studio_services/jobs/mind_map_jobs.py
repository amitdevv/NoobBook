"""
Mind Map Job Management - Tracks mind map generation jobs.

Educational Note: Mind map jobs use AI to analyze source content and create
hierarchical node structures for visual representation using React Flow.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "mind_map"


def create_mind_map_job(
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
        "nodes": [],
        "topic_summary": None,
        "node_count": 0,
        "generation_time_seconds": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_mind_map_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_mind_map_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_mind_map_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_mind_map_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
